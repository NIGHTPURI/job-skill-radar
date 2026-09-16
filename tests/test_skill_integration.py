"""Extraction changes through existing consumers; no new persistence policy."""
import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jobskillradar.analyzer import analyze_postings
from jobskillradar.recommender import recommend_skills
from jobskillradar.storage import ensure_schema, load_postings, save_postings


class SkillIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.addCleanup(self.conn.close)

    def skills(self):
        return self.conn.execute(
            "SELECT source, posting_id, skill FROM posting_skills ORDER BY source, posting_id, skill"
        ).fetchall()

    def test_expanded_skills_replace_atomically_and_keep_source_identity(self):
        base = {"source": "test", "posting_id": "1"}
        save_postings(self.conn, [
            {**base, "title": "SpringBoot", "description": "Python. Redis"},
            {**base, "source": "other", "title": "Kotlin"},
        ])
        self.assertEqual(self.skills(), [
            ("other", "1", "Kotlin"), ("test", "1", "Python"),
            ("test", "1", "Redis"), ("test", "1", "Spring Boot"),
        ])
        self.assertEqual(save_postings(self.conn, [{**base, "title": "GitHub Actions; JUnit"}]), 0)
        self.assertEqual(self.skills(), [
            ("other", "1", "Kotlin"), ("test", "1", "GitHub Actions"), ("test", "1", "JUnit"),
        ])
        analysis = analyze_postings(load_postings(self.conn))
        self.assertEqual(analysis["skill_counts"], {"Kotlin": 1, "GitHub Actions": 1, "JUnit": 1})
        self.assertEqual(self.conn.execute("PRAGMA user_version").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_new_skill_insert_failure_preserves_previous_representation(self):
        base = {"source": "test", "posting_id": "1"}
        save_postings(self.conn, [{**base, "title": "SpringBoot"}])
        self.conn.execute("""CREATE TRIGGER reject_redis BEFORE INSERT ON posting_skills
            WHEN NEW.skill='Redis' BEGIN SELECT RAISE(ABORT, 'injected failure'); END""")
        before = list(self.conn.iterdump())
        with self.assertRaisesRegex(sqlite3.IntegrityError, "injected failure"):
            save_postings(self.conn, [{**base, "title": "Redis"}])
        self.assertEqual(list(self.conn.iterdump()), before)
        self.assertFalse(self.conn.in_transaction)

    def test_existing_v1_skills_are_unchanged_on_read_and_refreshed_on_save(self):
        base = {"source": "test", "posting_id": "1", "title": "Python. SpringBoot R&D"}
        save_postings(self.conn, [base])
        # Represent the old extractor's persisted result, without auto backfill.
        self.conn.execute("DELETE FROM posting_skills")
        self.conn.execute("INSERT INTO posting_skills VALUES ('test', '1', 'R')")
        self.conn.commit()
        before = list(self.conn.iterdump())
        ensure_schema(self.conn)
        analysis = analyze_postings(load_postings(self.conn))
        self.assertEqual(analysis["skill_counts"], {"Python": 1, "Spring Boot": 1})
        self.assertEqual(list(self.conn.iterdump()), before)
        self.assertEqual(save_postings(self.conn, [base]), 0)
        self.assertEqual(self.skills(), [("test", "1", "Python"), ("test", "1", "Spring Boot")])

    def test_legacy_migration_uses_current_extractor_without_new_schema(self):
        schema = Path(__file__).parent / "fixtures" / "legacy_schema.sql"
        self.conn.executescript(schema.read_text(encoding="utf-8"))
        self.conn.execute("""INSERT INTO job_postings
            (source, posting_id, title, description, created_at)
            VALUES ('test', '1', 'SpringBoot', 'Python. R&D', '2000-01-01T00:00:00')""")
        self.conn.execute("INSERT INTO posting_skills VALUES ('1', 'R')")
        self.conn.commit()
        with self.assertLogs("jobskillradar.migrations", level="WARNING"):
            ensure_schema(self.conn)
        self.assertEqual(self.skills(), [("test", "1", "Python"), ("test", "1", "Spring Boot")])
        self.assertEqual(self.conn.execute("PRAGMA user_version").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("SELECT created_at FROM job_postings").fetchone()[0],
                         "2000-01-01T00:00:00")
        self.assertEqual(self.conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_owned_backend_aliases_filter_recommendations_preserving_market_evidence(self):
        analysis = analyze_postings([
            {"title": "Backend Engineer", "description": "SpringBoot Git Redis"},
            {"title": "Backend Engineer", "description": "스프링부트 깃 Redis"},
        ])
        result = recommend_skills("백엔드 엔지니어", ["스프링부트", "깃"], analysis, limit=5)
        self.assertEqual([(item["skill"], item["market_count"]) for item in result],
                         [("Redis", 2), ("REST API", 0), ("SQL", 0)])
        self.assertTrue(all(item["role_posting_count"] == 2 for item in result))


if __name__ == "__main__":
    unittest.main()
