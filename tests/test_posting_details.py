import sqlite3
import sys
import tempfile
import traceback
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jobskillradar import storage
from jobskillradar.models import DETAIL_TEXT_FIELDS
from jobskillradar.work24_client import parse_posting_detail

FIXTURE = Path(__file__).parent / "fixtures" / "work24" / "detail.xml"


def detail(posting_id="TEST-001", source="work24", **changes):
    return {**parse_posting_detail(FIXTURE.read_text(encoding="utf-8")),
            "source": source, "posting_id": posting_id,
            "fetched_at": "2026-09-16T01:00:00+00:00", **changes}


class PostingDetailStorageTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.addCleanup(self.conn.close)
        storage.save_postings(self.conn, [{"source": "work24", "posting_id": "TEST-001", "title": "SQL"}])

    def load(self, source="work24", posting_id="TEST-001"):
        return storage.load_posting_detail(self.conn, source, posting_id)

    def test_round_trip_identical_refresh_and_changed_observation(self):
        self.assertIsNone(self.load())
        original = detail()
        for refreshed in (original, original, detail(fetched_at="2026-09-17T01:00:00Z")):
            storage.save_posting_details(self.conn, [refreshed])
            self.assertEqual(self.load(), refreshed)
            self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM posting_details").fetchone()[0], 1)
        self.assertFalse(self.conn.in_transaction)

    def test_success_replaces_all_fields_and_preserves_parent(self):
        before = storage.load_postings(self.conn)
        created = self.conn.execute("SELECT created_at FROM job_postings").fetchall()
        storage.save_posting_details(self.conn, [detail()])
        changed = {"source": "work24", "posting_id": "TEST-001", "job_content": "Updated\n  source text",
                   "keywords": ['SQL', '한국어', 'SQL', 'quote"'], "fetched_at": "2026-09-17T00:00:00+00:00"}
        storage.save_posting_details(self.conn, [changed])
        loaded = self.load()
        self.assertEqual(loaded, {**dict.fromkeys(DETAIL_TEXT_FIELDS), **changed})
        self.assertEqual(storage.load_postings(self.conn), before)
        self.assertEqual(self.conn.execute("SELECT created_at FROM job_postings").fetchall(), created)
        self.assertEqual(self.conn.execute("SELECT skill FROM posting_skills").fetchall(), [("SQL",)])

    def test_invalid_identity_timestamp_and_value_reject_whole_batch(self):
        invalid = [{field: value} for field in ("source", "posting_id") for value in (None, "", " \t", 1)]
        invalid += [{"fetched_at": value} for value in (None, "", "secret-value", "2026-09-16",
                    "2026-09-16T01:00:00", "2026-09-16T01:00:00+09:00")]
        invalid += [{"keywords": None}, {"keywords": [1]}, {"job_content": 2}]
        for changes in invalid:
            with self.subTest(changes=changes):
                try:
                    storage.save_posting_details(self.conn, [detail(), detail(**changes)])
                except ValueError as error:
                    self.assertNotIn("secret-value", "".join(traceback.format_exception(error)))
                else:
                    self.fail("Invalid evidence accepted")
                self.assertIsNone(self.load())
        for identity in (("", "TEST-001"), ("work24", None)):
            with self.assertRaises(ValueError):
                storage.load_posting_detail(self.conn, *identity)

    def test_orphan_or_wrong_source_rolls_back_prior_update(self):
        original = detail()
        storage.save_posting_details(self.conn, [original])
        for orphan in (detail(posting_id="missing"), detail(source="other")):
            with self.assertRaises(sqlite3.IntegrityError):
                storage.save_posting_details(self.conn, [detail(job_content="changed"), orphan])
            self.assertEqual(self.load(), original)
            self.assertFalse(self.conn.in_transaction)

    def test_same_id_across_sources_and_cascade_are_independent(self):
        storage.save_postings(self.conn, [{"source": "other", "posting_id": "TEST-001", "title": "Java"}])
        storage.save_posting_details(self.conn, [detail(), detail(source="other", job_content="Other")])
        self.assertEqual(self.load("other")["job_content"], "Other")
        self.conn.execute("DELETE FROM job_postings WHERE source='work24'")
        self.conn.commit()
        self.assertIsNone(self.load())
        self.assertEqual(self.load("other"), detail(source="other", job_content="Other"))
        self.assertEqual(self.conn.execute("SELECT source, skill FROM posting_skills").fetchall(), [("other", "Java")])
        self.assertEqual(self.conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_savepoint_preserves_caller_transaction_on_success_and_failure(self):
        self.conn.execute("BEGIN")
        self.conn.execute("UPDATE job_postings SET company='caller'")
        storage.save_posting_details(self.conn, [detail()])
        with self.assertRaises(sqlite3.IntegrityError):
            storage.save_posting_details(self.conn, [detail(job_content="changed"), detail(posting_id="missing")])
        self.assertTrue(self.conn.in_transaction)
        self.assertEqual(self.load(), detail())
        self.assertEqual(self.conn.execute("SELECT company FROM job_postings").fetchone()[0], "caller")
        self.conn.rollback()
        self.assertIsNone(self.load())
        self.assertIsNone(storage.load_postings(self.conn)[0]["company"])

    def test_path_wrappers_reopen_and_close_on_success_and_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "details.sqlite"
            storage.save_postings_to_db(path, [{"source": "work24", "posting_id": "TEST-001"}])
            storage.save_posting_details_to_db(path, [detail()])
            self.assertEqual(storage.load_posting_detail_from_db(path, "work24", "TEST-001"), detail())
            for operation in ("save", "load"):
                for fail in (False, True):
                    with self.subTest(operation=operation, fail=fail):
                        conn = storage.connect(path)
                        identity = "" if fail else "TEST-001"
                        with patch.object(storage, "connect", return_value=conn):
                            def invoke():
                                if operation == "save":
                                    storage.save_posting_details_to_db(path, [detail(posting_id=identity)])
                                else:
                                    storage.load_posting_detail_from_db(path, "work24", identity)
                            if fail:
                                with self.assertRaises(ValueError):
                                    invoke()
                            else:
                                invoke()
                        with self.assertRaises(sqlite3.ProgrammingError):
                            conn.execute("SELECT 1")


if __name__ == "__main__":
    unittest.main()
