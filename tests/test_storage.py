from __future__ import annotations

import sys
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jobskillradar.normalizer import clean_postings
from jobskillradar.sample_data import SAMPLE_POSTINGS
from jobskillradar.storage import connect, count_postings, ensure_schema, load_postings, save_postings
from jobskillradar.skill_extractor import extract_skills


class StorageTest(unittest.TestCase):
    def test_save_and_load_postings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "radar.sqlite"
            postings = clean_postings(SAMPLE_POSTINGS[:2])

            conn = connect(db_path)
            try:
                saved = save_postings(conn, postings)
                loaded = load_postings(conn)
                count = count_postings(conn)
            finally:
                conn.close()

            self.assertEqual(saved, 2)
            self.assertEqual(count, 2)
            self.assertEqual(len(loaded), 2)


class StorageRegressionTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.addCleanup(self.conn.close)

    def skill_rows(self):
        return self.conn.execute("SELECT posting_id, skill FROM posting_skills ORDER BY posting_id, skill").fetchall()

    def test_schema_is_idempotent_with_expected_keys(self):
        ensure_schema(self.conn)
        ensure_schema(self.conn)
        tables = self.conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        self.assertEqual(tables, [("discovery_run_postings",), ("discovery_runs",), ("job_postings",), ("posting_details",), ("posting_skills",), ("user_profile",)])
        for table, expected in [("job_postings", {"source": 1, "posting_id": 2}),
                                ("posting_skills", {"source": 1, "posting_id": 2, "skill": 3})]:
            columns = self.conn.execute(f"PRAGMA table_info({table})").fetchall()
            self.assertEqual({row[1]: row[5] for row in columns if row[5]}, expected)

    def test_read_and_count_create_empty_schema(self):
        self.assertEqual(load_postings(self.conn), [])
        self.assertEqual(count_postings(self.conn), 0)

    def test_round_trip_all_fields_and_created_timestamp(self):
        posting = clean_postings(SAMPLE_POSTINGS[:1])[0]
        self.assertEqual(save_postings(self.conn, [posting]), 1)
        self.assertEqual(load_postings(self.conn), [posting])
        self.assertEqual(count_postings(self.conn), 1)
        created = self.conn.execute("SELECT created_at FROM job_postings").fetchone()[0]
        self.assertIsNone(datetime.fromisoformat(created).tzinfo)
        self.assertNotIn("created_at", load_postings(self.conn)[0])

    def test_missing_optional_fields_are_sql_null(self):
        self.assertEqual(save_postings(self.conn, [{"source": "test", "posting_id": "1"}]), 1)
        loaded = load_postings(self.conn)[0]
        self.assertEqual(loaded["source"], "test")
        self.assertEqual(loaded["posting_id"], "1")
        self.assertTrue(all(value is None for key, value in loaded.items() if key not in {"source", "posting_id"}))
        self.assertEqual(self.skill_rows(), [])

    def test_skills_extracted_once_from_title_and_description(self):
        save_postings(self.conn, [{"source": "test", "posting_id": "1", "title": "Python",
                                  "description": "파이썬 SQL SQL", "skills": ["Java"]}])
        self.assertEqual(self.skill_rows(), [("1", "Python"), ("1", "SQL")])

    def test_identical_repeat_save_is_idempotent(self):
        posting = {"source": "test", "posting_id": "1", "title": "Python SQL"}
        self.assertEqual(save_postings(self.conn, [posting]), 1)
        created = self.conn.execute("SELECT created_at FROM job_postings").fetchone()[0]
        self.assertEqual(save_postings(self.conn, [posting, posting]), 0)
        self.assertEqual(count_postings(self.conn), 1)
        self.assertEqual(self.skill_rows(), [("1", "Python"), ("1", "SQL")])
        self.assertEqual(self.conn.execute("SELECT created_at FROM job_postings").fetchone()[0], created)

    def save_changed_duplicate(self):
        original = {"source": "test", "posting_id": "1", "title": "Python developer", "description": "SQL"}
        changed = {**original, "title": "Java developer", "description": "Kafka"}
        first = save_postings(self.conn, [original])
        second = save_postings(self.conn, [changed])
        return first, second, load_postings(self.conn)[0]

    def test_changed_duplicate_replaces_content_and_skills(self):
        """KD-06 fixed: the latest representation replaces all previous skills."""
        first, second, stored = self.save_changed_duplicate()
        self.assertEqual((first, second, count_postings(self.conn)), (1, 0, 1))
        self.assertEqual((stored["title"], stored["description"]), ("Java developer", "Kafka"))
        self.assertEqual(self.skill_rows(), [("1", "Java"), ("1", "Kafka")])
        self.assertEqual(extract_skills(stored["title"], stored["description"]), ["Java", "Kafka"])

    def test_kd06_persisted_skills_should_agree_with_persisted_content(self):
        """KD-06 fixed: stored skills always agree with the saved representation."""
        _, _, stored = self.save_changed_duplicate()
        self.assertEqual({skill for _, skill in self.skill_rows()},
                         set(extract_skills(stored["title"], stored["description"])))

    def test_source_scopes_posting_identity(self):
        self.assertEqual(save_postings(self.conn, [{"source": "a", "posting_id": "1"},
                                                  {"source": "b", "posting_id": "1"}]), 2)
        self.assertEqual([p["source"] for p in load_postings(self.conn)], ["a", "b"])

    def test_load_order_uses_registered_date_then_id_descending(self):
        save_postings(self.conn, [
            {"source": "test", "posting_id": key, "registered_at": date}
            for key, date in [("a", "2026-01-02"), ("z", "2026-01-01"), ("b", "2026-01-02")]
        ])
        self.assertEqual([p["posting_id"] for p in load_postings(self.conn)], ["b", "a", "z"])

    def test_file_connection_creates_parent_and_commits_for_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "test.sqlite"
            conn = connect(path)
            try:
                save_postings(conn, [{"source": "test", "posting_id": "1"}])
            finally:
                conn.close()
            conn = connect(path)
            try:
                self.assertEqual(count_postings(conn), 1)
            finally:
                conn.close()

    def test_missing_source_is_rejected_without_orphan_skills(self):
        with self.assertRaisesRegex(ValueError, "source"):
            save_postings(self.conn, [{"posting_id": "orphan", "title": "Python"}])
        self.assertEqual(count_postings(self.conn), 0)
        self.assertEqual(self.skill_rows(), [])


if __name__ == "__main__":
    unittest.main()
