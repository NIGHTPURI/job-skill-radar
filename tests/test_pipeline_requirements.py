import copy
import importlib.util
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from jobskillradar import pipeline, storage
from jobskillradar.recommender import recommend_skills
from jobskillradar.requirement_extractor import extract_requirements
from jobskillradar.work24_client import Work24Error
from test_requirement_extractor import source_detail, classifications


class RequirementPipelineTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "requirements.sqlite"
        blocker = patch("urllib.request.urlopen", side_effect=AssertionError("Unexpected HTTP"))
        blocker.start()
        self.addCleanup(blocker.stop)
        storage.save_postings_to_db(self.path, [{"source": "work24", "posting_id": "synthetic",
                                               "title": "Backend Engineer", "description": "Java SQL", "career": "무관"}])

    def load(self, source="work24"):
        return pipeline.load_posting_requirements(source, "synthetic", db_path=self.path)

    def dump(self):
        with closing(storage.connect(self.path)) as conn:
            return list(conn.iterdump())

    def test_missing_detail_is_explicit_for_the_requested_identity(self):
        result = self.load()
        self.assertEqual(result["quality_status"], "detail_not_fetched")
        self.assertEqual((result["source"], result["posting_id"]), ("work24", "synthetic"))
        self.assertEqual(result["skills"], [])
        self.assertIsNone(result["detail_fetched_at"])

    def test_read_closes_connection_before_extraction_and_never_changes_rows(self):
        detail = source_detail(job_content="Requirements\nPython", preferred_conditions="Docker")
        storage.save_posting_details_to_db(self.path, [detail])
        before = self.dump()
        conn = storage.connect(self.path)
        def extract_after_close(value):
            with self.assertRaises(sqlite3.ProgrammingError):
                conn.execute("SELECT 1")
            with closing(sqlite3.connect(self.path, timeout=0)) as probe:
                probe.execute("BEGIN IMMEDIATE")
                probe.rollback()
            return extract_requirements(value)
        with patch.object(storage, "connect", return_value=conn), \
                patch.object(pipeline, "extract_requirements", side_effect=extract_after_close):
            result = self.load()
        self.assertEqual(result, extract_requirements(detail))
        self.assertEqual(self.dump(), before)

    def test_reprocessing_reads_latest_detail_without_stale_accumulation(self):
        storage.save_posting_details_to_db(self.path, [source_detail(job_content="Java 필수")])
        old_result = self.load()
        self.assertEqual(old_result, self.load())
        storage.save_posting_details_to_db(self.path, [source_detail(job_content="Python 우대", fetched_at="2026-09-18T00:00:00Z")])
        new_result = self.load()
        self.assertEqual(classifications(new_result), {"Python": "preferred"})
        self.assertEqual(new_result["detail_fetched_at"], "2026-09-18T00:00:00Z")
        self.assertEqual(classifications(old_result), {"Java": "required"})
        with closing(storage.connect(self.path)) as conn:
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 4)
            self.assertEqual(conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall(),
                             [("discovery_run_postings",), ("discovery_runs",), ("job_postings",), ("posting_details",), ("posting_skills",), ("user_profile",)])

    def test_failed_detail_refresh_preserves_raw_and_recomputed_requirements(self):
        detail = source_detail(job_content="Java 필수")
        storage.save_posting_details_to_db(self.path, [detail])
        old_result = self.load()
        result = pipeline.collect_work24_with_details_to_db(
            "fake", ["Java"], db_path=self.path,
            collector=Mock(return_value=[{"source": "work24", "posting_id": "synthetic"}]),
            detail_fetcher=Mock(side_effect=Work24Error("transport_error")))
        self.assertEqual(len(result["detail_failures"]), 1)
        self.assertEqual(storage.load_posting_detail_from_db(self.path, "work24", "synthetic"), detail)
        self.assertEqual(self.load(), old_result)

    def test_unexpected_extraction_failure_is_visible_without_erasing_any_data(self):
        storage.save_posting_details_to_db(self.path, [source_detail(job_content="Java 필수")])
        old_result = self.load()
        old_copy = copy.deepcopy(old_result)
        # A successful later raw refresh is independent of on-demand extraction.
        latest = source_detail(job_content="Python 우대")
        storage.save_posting_details_to_db(self.path, [latest])
        before = self.dump()
        with patch.object(pipeline, "extract_requirements", side_effect=RuntimeError("injected extraction failure")):
            with self.assertRaisesRegex(RuntimeError, "injected extraction failure"):
                self.load()
        self.assertEqual(self.dump(), before)
        self.assertEqual(old_result, old_copy)
        self.assertEqual(storage.load_posting_detail_from_db(self.path, "work24", "synthetic"), latest)
        self.assertEqual(classifications(self.load()), {"Python": "preferred"})

    def test_composite_identity_and_cascade_remain_source_specific(self):
        storage.save_postings_to_db(self.path, [{"source": "other", "posting_id": "synthetic"}])
        storage.save_posting_details_to_db(self.path, [source_detail(job_content="Java 필수"),
            source_detail(source="other", job_content="Python 우대")])
        self.assertEqual(classifications(self.load()), {"Java": "required"})
        self.assertEqual(classifications(self.load("other")), {"Python": "preferred"})
        with closing(storage.connect(self.path)) as conn:
            conn.execute("DELETE FROM job_postings WHERE source='work24'")
            conn.commit()
        self.assertEqual(self.load()["quality_status"], "detail_not_fetched")
        self.assertEqual(classifications(self.load("other")), {"Python": "preferred"})

    def test_market_analysis_and_recommendations_remain_separate(self):
        before = pipeline.load_db_analysis(db_path=self.path)
        storage.save_posting_details_to_db(self.path, [source_detail(job_content="Python required", keywords=["Kubernetes"])])
        self.assertEqual(classifications(self.load()), {"Python": "required", "Kubernetes": "unspecified"})
        after = pipeline.load_db_analysis(db_path=self.path)
        self.assertEqual(after, before)
        self.assertEqual(after["skill_counts"], {"Java": 1, "SQL": 1})
        self.assertEqual(recommend_skills("백엔드 엔지니어", [], after), recommend_skills("백엔드 엔지니어", [], before))

    def test_inspection_cli_returns_provenance_and_missing_state_without_network(self):
        spec = importlib.util.spec_from_file_location("inspect_requirements_cli", ROOT / "scripts" / "inspect_requirements.py")
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        for fetched in (False, True):
            if fetched:
                storage.save_posting_details_to_db(self.path, [source_detail(job_content="Java 필수")])
            output = io.StringIO()
            with patch.object(sys, "argv", ["inspect_requirements.py", "--posting-id", "synthetic", "--db-path", str(self.path)]), redirect_stdout(output):
                cli.main()
            self.assertEqual(json.loads(output.getvalue()), self.load())


if __name__ == "__main__":
    unittest.main()
