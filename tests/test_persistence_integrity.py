import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jobskillradar.storage import ensure_schema, load_postings, save_postings
from jobskillradar.normalizer import clean_posting, normalize_career


class PersistenceIntegrityTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.addCleanup(self.conn.close)
        ensure_schema(self.conn)

    def skills(self):
        return self.conn.execute("SELECT source, posting_id, skill FROM posting_skills ORDER BY source, posting_id, skill").fetchall()

    def test_same_external_id_distinct_sources_have_distinct_skills(self):
        self.assertEqual(save_postings(self.conn, [
            {"source": "work24", "posting_id": "123", "title": "Python"},
            {"source": "another_source", "posting_id": "123", "title": "Java"},
        ]), 2)
        self.assertEqual(self.skills(), [("another_source", "123", "Java"), ("work24", "123", "Python")])
        save_postings(self.conn, [{"source": "work24", "posting_id": "123", "title": "SQL"}])
        self.assertEqual(self.skills(), [("another_source", "123", "Java"), ("work24", "123", "SQL")])
        self.assertEqual(len(load_postings(self.conn)), 2)

    def test_removed_added_and_empty_skill_set_exactly_replace_previous(self):
        base = {"source": "work24", "posting_id": "1"}
        for title, expected in [("Python SQL", ["Python", "SQL"]), ("SQL Java", ["Java", "SQL"]), ("specialist", [])]:
            with self.subTest(title=title):
                save_postings(self.conn, [{**base, "title": title}])
                self.assertEqual(self.skills(), [("work24", "1", skill) for skill in expected])
                self.assertEqual(load_postings(self.conn)[0]["title"], title)

    def test_invalid_identities_reject_entire_batch_without_writes(self):
        for field in ("source", "posting_id"):
            for value in (None, "", " \t\n", 123):
                with self.subTest(field=field, value=value):
                    invalid = {"source": "test", "posting_id": "bad", "title": "Java", field: value}
                    with self.assertRaisesRegex(ValueError, field):
                        save_postings(self.conn, [{"source": "test", "posting_id": "good", "title": "Python"}, invalid])
                    self.assertEqual(load_postings(self.conn), [])
                    self.assertEqual(self.skills(), [])

    def test_missing_posting_id_rejected(self):
        with self.assertRaisesRegex(ValueError, "posting_id"):
            save_postings(self.conn, [{"source": "test", "title": "Python"}])
        self.assertEqual(self.skills(), [])

    def test_foreign_key_blocks_orphans_and_wrong_source(self):
        self.assertEqual(self.conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        save_postings(self.conn, [{"source": "a", "posting_id": "1"}])
        for identity in [("a", "missing"), ("b", "1")]:
            with self.subTest(identity=identity):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.conn.execute("INSERT INTO posting_skills VALUES (?, ?, 'SQL')", identity)
                self.conn.rollback()
        self.assertEqual(self.skills(), [])

    def test_parent_delete_cascades_only_matching_source(self):
        save_postings(self.conn, [{"source": source, "posting_id": "1", "title": "SQL"} for source in ("a", "b")])
        self.conn.execute("DELETE FROM job_postings WHERE source='a' AND posting_id='1'")
        self.conn.commit()
        self.assertEqual(self.skills(), [("b", "1", "SQL")])
        self.assertEqual(self.conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_database_rejects_null_and_blank_identities(self):
        for source, posting_id in [(None, "1"), ("a", None), ("", "1"), ("a", " \t")]:
            with self.subTest(source=source, posting_id=posting_id):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.conn.execute("INSERT INTO job_postings (source,posting_id,created_at) VALUES (?,?,?)",
                                      (source, posting_id, "time"))
                self.conn.rollback()

    def test_created_at_preserved_on_changed_save(self):
        save_postings(self.conn, [{"source": "test", "posting_id": "1", "title": "Python"}])
        self.conn.execute("UPDATE job_postings SET created_at='2000-01-01T00:00:00'")
        self.conn.commit()
        save_postings(self.conn, [{"source": "test", "posting_id": "1", "title": "Java"}])
        self.assertEqual(self.conn.execute("SELECT created_at FROM job_postings").fetchone()[0], "2000-01-01T00:00:00")

    def test_full_replacement_sets_omitted_optional_fields_to_null(self):
        save_postings(self.conn, [{"source": "test", "posting_id": "1", "title": "Python", "description": "SQL"}])
        save_postings(self.conn, [{"source": "test", "posting_id": "1", "title": "Java"}])
        self.assertIsNone(load_postings(self.conn)[0]["description"])
        self.assertEqual(self.skills(), [("test", "1", "Java")])

    def test_repeated_identity_in_direct_batch_last_wins_and_counts_one_new(self):
        self.assertEqual(save_postings(self.conn, [
            {"source": "test", "posting_id": "1", "title": title} for title in ("Python", "Java")
        ]), 1)
        self.assertEqual(self.skills(), [("test", "1", "Java")])

    def test_child_insert_failure_rolls_back_all_postings_and_skill_changes(self):
        save_postings(self.conn, [{"source": "test", "posting_id": "old", "title": "Python"}])
        before = load_postings(self.conn)
        self.conn.execute("""CREATE TRIGGER reject_java BEFORE INSERT ON posting_skills
            WHEN NEW.skill='Java' BEGIN SELECT RAISE(ABORT, 'injected skill failure'); END""")
        with self.assertRaisesRegex(sqlite3.IntegrityError, "injected skill failure"):
            save_postings(self.conn, [
                {"source": "test", "posting_id": "new", "title": "SQL"},
                {"source": "test", "posting_id": "old", "title": "Java"},
            ])
        self.assertEqual(load_postings(self.conn), before)
        self.assertEqual(self.skills(), [("test", "old", "Python")])
        self.assertFalse(self.conn.in_transaction)

    def test_successful_save_inside_caller_transaction_does_not_commit_it(self):
        self.conn.execute("BEGIN")
        save_postings(self.conn, [{"source": "test", "posting_id": "1", "title": "Python"}])
        self.assertTrue(self.conn.in_transaction)
        self.conn.rollback()
        self.assertEqual(load_postings(self.conn), [])
        self.assertEqual(self.skills(), [])

    def test_failed_save_preserves_prior_caller_work(self):
        self.conn.execute("BEGIN")
        self.conn.execute("INSERT INTO job_postings (source,posting_id,created_at) VALUES ('test','outer','time')")
        with self.assertRaises(sqlite3.ProgrammingError):
            save_postings(self.conn, [{"source": "test", "posting_id": "bad", "title": object()}])
        self.assertTrue(self.conn.in_transaction)
        self.assertEqual([p["posting_id"] for p in load_postings(self.conn)], ["outer"])
        self.conn.rollback()

    def test_foreign_keys_disabled_in_active_transaction_are_rejected(self):
        self.conn.execute("PRAGMA foreign_keys=OFF")
        self.conn.execute("BEGIN")
        with self.assertRaisesRegex(RuntimeError, "foreign keys"):
            save_postings(self.conn, [{"source": "test", "posting_id": "1"}])
        self.assertTrue(self.conn.in_transaction)
        self.conn.rollback()
        self.assertEqual(load_postings(self.conn), [])
        self.assertEqual(self.conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)

    def test_normalized_fields_are_idempotent_including_missing_career(self):
        for career in (None, "", " ", "미상", "기타", "신입", "경력", "경력 3년", "경력무관",
                       "무관", "관계없음", "신입/경력", "경력 / 신입"):
            for region in (None, "", "미상", "서울특별시 강남구", "overseas city"):
                with self.subTest(career=career, region=region):
                    raw = {"source": " test ", "posting_id": " 1 ", "career": career, "region": region,
                           "title": " SQL ", "salary": None, "registered_at": " 2026-09-16 "}
                    cleaned = clean_posting(raw)
                    self.assertEqual(clean_posting(cleaned), cleaned)
                    save_postings(self.conn, [cleaned])
                    self.assertEqual(clean_posting(load_postings(self.conn)[0]), cleaned)
        self.assertEqual(normalize_career(None), "미상")
        self.assertEqual(normalize_career("미상"), "미상")
        self.assertEqual(normalize_career("경력무관"), "무관")
        self.assertEqual(normalize_career("신입/경력"), "신입/경력")


if __name__ == "__main__":
    unittest.main()
