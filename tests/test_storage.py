from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jobskillradar.normalizer import clean_postings
from jobskillradar.sample_data import SAMPLE_POSTINGS
from jobskillradar.storage import connect, count_postings, load_postings, save_postings


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


if __name__ == "__main__":
    unittest.main()
