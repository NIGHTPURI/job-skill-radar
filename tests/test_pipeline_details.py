import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jobskillradar import pipeline, storage
from jobskillradar.recommender import recommend_skills
from jobskillradar.work24_client import Work24Error
from test_posting_details import detail


class DetailPipelineTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "pipeline.sqlite"
        blocker = patch("urllib.request.urlopen", side_effect=AssertionError("Unexpected network"))
        blocker.start()
        self.addCleanup(blocker.stop)

    def collect(self, postings, fetcher):
        return pipeline.collect_work24_with_details_to_db(
            "fake", ["backend"], db_path=self.path,
            collector=Mock(return_value=postings), detail_fetcher=fetcher)

    def test_twenty_postings_with_one_failure_preserve_nineteen_successes(self):
        postings = [{"source": "work24", "posting_id": str(index)} for index in range(20)]
        def fetch(**kwargs):
            posting_id = kwargs["wanted_auth_no"]
            if posting_id == "7":
                raise Work24Error("transport_error")
            return detail(posting_id=posting_id)
        result = self.collect(postings, fetch)
        self.assertEqual(result, {"collected": 20, "new_postings": 20, "details_saved": 19,
                                  "detail_failures": [{"source": "work24", "posting_id": "7", "reason": "transport_error"}]})
        self.assertEqual(len(storage.load_postings_from_db(self.path)), 20)
        for index in range(20):
            stored = storage.load_posting_detail_from_db(self.path, "work24", str(index))
            self.assertEqual(stored, None if index == 7 else detail(posting_id=str(index)))

    def test_failed_refresh_preserves_old_detail_while_other_refreshes_succeed(self):
        postings = [{"source": "work24", "posting_id": str(index)} for index in range(20)]
        first = self.collect(postings, lambda **kw: detail(posting_id=kw["wanted_auth_no"]))
        self.assertEqual(first["details_saved"], 20)
        old = storage.load_posting_detail_from_db(self.path, "work24", "7")
        def refresh(**kwargs):
            if kwargs["wanted_auth_no"] == "7":
                raise Work24Error("api_error")
            return detail(posting_id=kwargs["wanted_auth_no"], job_content="Refreshed",
                          fetched_at="2026-09-17T00:00:00+00:00")
        result = self.collect(postings, refresh)
        self.assertEqual((result["new_postings"], result["details_saved"]), (0, 19))
        self.assertEqual(result["detail_failures"], [{"source": "work24", "posting_id": "7", "reason": "api_error"}])
        self.assertEqual(storage.load_posting_detail_from_db(self.path, "work24", "7"), old)
        for index in range(20):
            if index != 7:
                self.assertEqual(storage.load_posting_detail_from_db(self.path, "work24", str(index)),
                                 refresh(wanted_auth_no=str(index)))

    def test_duplicate_identities_across_keywords_fetch_once_after_normalization(self):
        collector = Mock(side_effect=[
            [{"source": " work24 ", "posting_id": " 1 ", "title": "First"}] * 2,
            [{"source": "work24", "posting_id": "1", "title": "Later"},
             {"source": "work24", "posting_id": "2"}, {"title": "No identity"}],
        ])
        fetch = Mock(side_effect=lambda **kw: detail(posting_id=kw["wanted_auth_no"]))
        result = pipeline.collect_work24_with_details_to_db(
            "fake", ["first", "second"], pages=2, db_path=self.path,
            collector=collector, detail_fetcher=fetch)
        self.assertEqual((result["collected"], result["details_saved"]), (2, 2))
        self.assertEqual([call.kwargs for call in fetch.call_args_list],
                         [{"auth_key": "fake", "wanted_auth_no": value} for value in ("1", "2")])
        rows = {p["posting_id"]: p for p in storage.load_postings_from_db(self.path)}
        self.assertEqual(rows["1"]["title"], "First")

    def test_http_boundaries_have_no_open_storage_connection_or_write_transaction(self):
        connections = []
        connect = storage.connect
        def track(path):
            conn = connect(path)
            connections.append(conn)
            return conn
        def assert_closed():
            for conn in connections:
                with self.assertRaises(sqlite3.ProgrammingError):
                    conn.execute("SELECT 1")
        def collect(**kwargs):
            assert_closed()
            return [{"source": "work24", "posting_id": value} for value in ("1", "2")]
        def fetch(**kwargs):
            assert_closed()
            # A separate writer can acquire the lock, and the entire list is visible.
            with closing(sqlite3.connect(self.path, timeout=0)) as probe:
                probe.execute("BEGIN IMMEDIATE")
                self.assertEqual(probe.execute("SELECT COUNT(*) FROM job_postings").fetchone()[0], 2)
                probe.rollback()
            return detail(posting_id=kwargs["wanted_auth_no"])
        with patch.object(storage, "connect", side_effect=track):
            result = pipeline.collect_work24_with_details_to_db(
                "fake", ["one", "two"], db_path=self.path, collector=collect, detail_fetcher=fetch)
        self.assertEqual(result["details_saved"], 2)
        self.assertEqual(len(connections), 3)
        assert_closed()

    def test_list_only_keeps_int_contract_without_detail_requests(self):
        with patch.object(pipeline, "fetch_posting_detail", side_effect=AssertionError("Detail disabled")) as fetch:
            result = pipeline.collect_work24_to_db("fake", ["one"], db_path=self.path,
                collector=Mock(return_value=[{"source": "work24", "posting_id": "1"}]))
        self.assertIs(type(result), int)
        self.assertEqual(result, 1)
        fetch.assert_not_called()
        self.assertIsNone(storage.load_posting_detail_from_db(self.path, "work24", "1"))

    def test_detail_evidence_does_not_change_analysis_skills_career_or_recommendations(self):
        postings = [{"source": "work24", "posting_id": "1", "title": "Backend Engineer",
                     "description": "Java SQL", "career": "경력무관"}]
        storage.save_postings_to_db(self.path, pipeline.clean_postings(postings))
        before = pipeline.load_db_analysis(db_path=self.path)
        self.collect(postings, lambda **kw: detail(posting_id="1", job_content="Python PyTorch ML engineer",
                     preferred_conditions="Docker", other_preferred_conditions="Kubernetes",
                     certificate="AWS", keywords=["Redis"], raw_career_condition="경력무관"))
        after = pipeline.load_db_analysis(db_path=self.path)
        self.assertEqual(after, before)
        self.assertEqual(after["career_counts"], {"무관": 1})
        self.assertEqual(after["skill_counts"], {"Java": 1, "SQL": 1})
        self.assertEqual(recommend_skills("백엔드 엔지니어", [], after),
                         recommend_skills("백엔드 엔지니어", [], before))
        self.assertEqual(storage.load_posting_detail_from_db(self.path, "work24", "1")["raw_career_condition"], "경력무관")
        with closing(storage.connect(self.path)) as conn:
            self.assertEqual(conn.execute("SELECT skill FROM posting_skills ORDER BY skill").fetchall(), [("Java",), ("SQL",)])

    def test_wrong_identity_is_reported_without_saving_fabricated_detail(self):
        result = self.collect([{"source": "work24", "posting_id": "1"}], Mock(return_value=detail(posting_id="2")))
        self.assertEqual(result["details_saved"], 0)
        self.assertEqual(result["detail_failures"][0]["reason"], "identity_mismatch")
        self.assertIsNone(storage.load_posting_detail_from_db(self.path, "work24", "1"))


if __name__ == "__main__":
    unittest.main()
