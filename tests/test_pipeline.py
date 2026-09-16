import sqlite3
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jobskillradar import pipeline, storage
from jobskillradar.recommender import recommend_skills
from jobskillradar.storage import connect, save_postings


class PipelineTest(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.root = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        self.db_path = self.root / "radar.sqlite"
        stack.enter_context(patch.object(pipeline, "get_db_path", return_value=self.db_path))
        # Any accidental real HTTP access fails immediately, even outside the collector mock.
        stack.enter_context(patch("urllib.request.urlopen", side_effect=AssertionError("Network forbidden in pipeline tests")))
        self.fetch = stack.enter_context(patch.object(pipeline, "fetch_work24_postings", return_value=[]))

    def test_sample_baseline_counts_and_recommendation_order(self):
        analysis = pipeline.analyze_sample()
        self.assertEqual(len(analysis["postings"]), 12)
        self.assertEqual(analysis["role_counts"], {
            "데이터 분석가": 6, "데이터 엔지니어": 2, "ML 엔지니어": 3, "BI 분석가": 1,
        })
        self.assertEqual(analysis["skill_counts"], {
            "Python": 8, "SQL": 6, "Machine Learning": 3, "A/B Test": 2,
            "Tableau": 2, "Power BI": 2, "Airflow": 2, "AWS": 2,
            "PostgreSQL": 2, "NLP": 2, "PyTorch": 2, "Docker": 2,
            "Statistics": 2, "Excel": 1, "Spark": 1, "Kafka": 1,
            "TensorFlow": 1, "Pandas": 1, "NumPy": 1, "Looker": 1,
            "Kubernetes": 1, "MySQL": 1, "Deep Learning": 1, "R": 1,
            "GA4": 1, "Recommender System": 1, "Plotly": 1,
        })
        recommendations = recommend_skills("데이터 분석가", ["SQL"], analysis, 5)
        self.assertEqual([(r["skill"], r["market_count"]) for r in recommendations],
                         [("Python", 5), ("A/B Test", 2), ("Tableau", 2), ("Statistics", 1), ("GA4", 1)])
        self.assertEqual([r["priority"] for r in recommendations], [1, 2, 3, 4, 5])
        self.assertTrue(all(r["role_posting_count"] == 6 for r in recommendations))
        self.assertFalse(self.db_path.exists())
        self.fetch.assert_not_called()

    def test_empty_db_analysis_returns_none_and_creates_db(self):
        self.assertIsNone(pipeline.load_db_analysis())
        self.assertTrue(self.db_path.exists())

    def test_seed_twice_and_load_full_sample_analysis(self):
        self.assertEqual(pipeline.seed_sample_db(), 12)
        self.assertEqual(pipeline.seed_sample_db(), 0)
        stored = pipeline.load_db_analysis()
        sample = pipeline.analyze_sample()
        for key in ("skill_counts", "role_counts", "career_counts", "region_counts", "role_skill_counts"):
            self.assertEqual(stored[key], sample[key])
        self.assertEqual(sorted(stored["postings"], key=lambda p: p["posting_id"]), sample["postings"])
        self.assertEqual(recommend_skills("데이터 분석가", ["SQL"], stored),
                         recommend_skills("데이터 분석가", ["SQL"], sample))

    def test_collection_normalizes_and_deduplicates_across_keywords(self):
        self.fetch.side_effect = [
            [{"source": "work24", "posting_id": "1", "title": " SQL ", "region": "서울 강남구"}],
            [{"source": "work24", "posting_id": "1", "title": "Java"},
             {"source": "work24", "posting_id": "2", "title": "Python"}, {"title": "no id"}],
        ]
        self.assertEqual(pipeline.collect_work24_to_db("fake-key", ["first", "second"], pages=2, display=20), 2)
        self.assertEqual([call.kwargs for call in self.fetch.call_args_list], [
            {"auth_key": "fake-key", "keyword": keyword, "pages": 2, "display": 20}
            for keyword in ["first", "second"]
        ])
        postings = {p["posting_id"]: p for p in pipeline.load_db_analysis()["postings"]}
        self.assertEqual(postings["1"]["title"], "SQL")
        self.assertEqual(postings["1"]["region"], "서울")
        self.assertEqual(postings["2"]["skills"], ["Python"])

    def test_empty_keyword_list_uses_current_defaults(self):
        self.assertEqual(pipeline.collect_work24_to_db("fake-key", []), 0)
        self.assertEqual([call.kwargs["keyword"] for call in self.fetch.call_args_list],
                         ["데이터 분석가", "데이터 엔지니어", "머신러닝", "SQL", "Python"])

    def test_collect_and_analyze_deduplicates_without_creating_db(self):
        self.fetch.return_value = [{"source": "test", "posting_id": "1", "title": "SQL"}]
        result = pipeline.collect_and_analyze("fake-key", ["one", "two"])
        self.assertEqual(len(result["postings"]), 1)
        self.assertEqual(result["skill_counts"], {"SQL": 1})
        self.assertFalse(self.db_path.exists())

    def test_current_later_collection_failure_discards_batch_preserves_existing_db(self):
        pipeline.seed_sample_db()
        before = pipeline.load_db_analysis()
        self.fetch.side_effect = [[{"source": "test", "posting_id": "new", "title": "Java"}], TimeoutError("offline")]
        with self.assertRaises(TimeoutError):
            pipeline.collect_work24_to_db("fake-key", ["first", "second"])
        self.assertEqual(pipeline.load_db_analysis(), before)

    def test_current_db_analysis_reextracts_instead_of_reading_skill_rows(self):
        conn = connect(self.db_path)
        try:
            save_postings(conn, [{"source": "test", "posting_id": "1", "title": "Python"}])
            conn.execute("UPDATE posting_skills SET skill='Java'")
            conn.commit()
        finally:
            conn.close()
        self.assertEqual(pipeline.load_db_analysis()["skill_counts"], {"Python": 1})

    def test_db_connection_is_closed_on_success_and_read_failure(self):
        for fail in (False, True):
            with self.subTest(fail=fail):
                conn = connect(self.db_path)
                with patch.object(storage, "connect", return_value=conn):
                    if fail:
                        with patch.object(storage, "load_postings", side_effect=sqlite3.OperationalError("read failed")):
                            with self.assertRaises(sqlite3.OperationalError):
                                pipeline.load_db_analysis()
                    else:
                        self.assertIsNone(pipeline.load_db_analysis())
                with self.assertRaises(sqlite3.ProgrammingError):
                    conn.execute("SELECT 1")


if __name__ == "__main__":
    unittest.main()
