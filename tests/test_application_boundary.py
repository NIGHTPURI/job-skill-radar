import sqlite3
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jobskillradar import pipeline
from jobskillradar.storage import save_postings_to_db


class ApplicationBoundaryTest(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.path = Path(stack.enter_context(tempfile.TemporaryDirectory())) / "explicit.sqlite"
        # Explicit boundaries must not read user config or access the real API.
        stack.enter_context(patch.object(pipeline, "get_db_path", side_effect=AssertionError("Unexpected config access")))
        stack.enter_context(patch("urllib.request.urlopen", side_effect=AssertionError("Unexpected network access")))

    def test_sample_mode_does_not_open_db(self):
        result, source = pipeline.load_analysis("샘플", db_path=self.path)
        self.assertEqual((source, len(result["postings"])), ("샘플", 12))
        self.assertFalse(self.path.exists())

    def test_unknown_mode_keeps_legacy_sample_fallback(self):
        self.assertEqual(pipeline.load_analysis("other", db_path=self.path),
                         pipeline.load_analysis("샘플", db_path=self.path))
        self.assertFalse(self.path.exists())

    def test_empty_db_first_returns_sample_and_creates_db(self):
        result, source = pipeline.load_analysis("DB 우선", db_path=self.path)
        self.assertEqual(source, "샘플")
        self.assertEqual(result, pipeline.analyze_sample())
        self.assertTrue(self.path.exists())

    def test_nonempty_db_first_uses_db_even_with_no_skills(self):
        save_postings_to_db(self.path, [{"source": "test", "posting_id": "one", "title": "specialist"}])
        result, source = pipeline.load_analysis("DB 우선", db_path=self.path)
        self.assertEqual(source, "DB")
        self.assertEqual(len(result["postings"]), 1)
        self.assertEqual(result["skill_counts"], {})

    def test_db_error_propagates_without_sample_fallback(self):
        self.path.write_bytes(b"not a sqlite database")
        with self.assertRaises(sqlite3.DatabaseError):
            pipeline.load_analysis("DB 우선", db_path=self.path)

    def test_explicit_seed_path_bypasses_config(self):
        self.assertEqual(pipeline.seed_sample_db(db_path=self.path), 12)
        self.assertEqual(pipeline.seed_sample_db(db_path=self.path), 0)
        self.assertEqual(pipeline.load_analysis("DB 우선", db_path=self.path)[1], "DB")

    def test_injected_collector_returns_normalized_first_id_without_persistence(self):
        collector = Mock(side_effect=[
            [{"source": "a", "posting_id": " 1 ", "title": " SQL ", "region": "서울 강남구"}],
            [{"source": "b", "posting_id": "1", "title": "Java"}, {"title": "no id"}],
        ])
        postings = pipeline.collect_postings("fake-key", ["first", "second"], 2, 20, collector=collector)
        self.assertEqual(len(postings), 2)
        self.assertEqual((postings[0]["source"], postings[0]["posting_id"], postings[0]["title"], postings[0]["region"]),
                         ("a", "1", "SQL", "서울"))
        self.assertEqual([call.kwargs for call in collector.call_args_list], [
            {"auth_key": "fake-key", "keyword": keyword, "pages": 2, "display": 20}
            for keyword in ["first", "second"]
        ])
        self.assertFalse(self.path.exists())

    def test_direct_analysis_and_saved_analysis_agree(self):
        collector = Mock(return_value=[{"source": "test", "posting_id": "1", "title": "SQL Python", "career": "신입"}])
        direct = pipeline.collect_and_analyze("fake-key", ["SQL"], collector=collector)
        self.assertFalse(self.path.exists())
        self.assertEqual(pipeline.collect_work24_to_db("fake-key", ["SQL"], db_path=self.path, collector=collector), 1)
        self.assertEqual(pipeline.load_db_analysis(db_path=self.path), direct)

    def test_missing_career_is_stable_after_storage_round_trip(self):
        """KD-11 fixed: canonical missing career survives repeated normalization."""
        collector = Mock(return_value=[{"source": "test", "posting_id": "1", "title": "SQL"}])
        direct = pipeline.collect_and_analyze("fake-key", ["SQL"], collector=collector)
        pipeline.collect_work24_to_db("fake-key", ["SQL"], db_path=self.path, collector=collector)
        loaded = pipeline.load_db_analysis(db_path=self.path)
        self.assertEqual(direct["career_counts"], {"미상": 1})
        self.assertEqual(loaded["career_counts"], {"미상": 1})
        self.assertEqual(direct["skill_counts"], loaded["skill_counts"])

    def test_collection_failure_does_not_open_destination(self):
        collector = Mock(side_effect=[[{"source": "test", "posting_id": "1"}], TimeoutError("offline")])
        with self.assertRaises(TimeoutError):
            pipeline.collect_work24_to_db("fake-key", ["first", "second"], db_path=self.path, collector=collector)
        self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()
