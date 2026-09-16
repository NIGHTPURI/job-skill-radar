import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jobskillradar import storage


class StorageBoundaryTest(unittest.TestCase):
    def test_path_boundary_preserves_partial_null_and_duplicate_behavior(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.sqlite"
            self.assertEqual(storage.save_postings_to_db(path, [{"source": "test", "posting_id": "1", "title": "Python"}]), 1)
            self.assertEqual(storage.save_postings_to_db(path, [{"source": "test", "posting_id": "1", "title": "Java"}]), 0)
            posting = storage.load_postings_from_db(path)[0]
            self.assertEqual(posting["title"], "Java")
            self.assertIsNone(posting["description"])
            conn = storage.connect(path)
            try:
                self.assertEqual(conn.execute("SELECT skill FROM posting_skills ORDER BY skill").fetchall(),
                                 [("Java",)])
            finally:
                conn.close()

    def test_save_connection_is_closed_on_success_and_failure(self):
        for fail in (False, True):
            with self.subTest(fail=fail):
                conn = sqlite3.connect(":memory:")
                with patch.object(storage, "connect", return_value=conn):
                    if fail:
                        with patch.object(storage, "save_postings", side_effect=sqlite3.OperationalError("write failed")):
                            with self.assertRaisesRegex(sqlite3.OperationalError, "write failed"):
                                storage.save_postings_to_db(Path("unused"), [])
                    else:
                        self.assertEqual(storage.save_postings_to_db(Path("unused"), []), 0)
                with self.assertRaises(sqlite3.ProgrammingError):
                    conn.execute("SELECT 1")

    def test_path_boundary_rejects_invalid_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.sqlite"
            with self.assertRaises(ValueError):
                storage.save_postings_to_db(path, [{"posting_id": "1", "title": "Python"}])
            self.assertEqual(storage.load_postings_from_db(path), [])
            conn = storage.connect(path)
            try:
                self.assertEqual(conn.execute("SELECT posting_id, skill FROM posting_skills").fetchall(), [])
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
