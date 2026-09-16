import sqlite3
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jobskillradar import migrations, storage

LEGACY_SCHEMA = (Path(__file__).parent / "fixtures" / "legacy_schema.sql").read_text(encoding="utf-8")


def legacy_posting(conn, posting_id="1", source="work24", title="Python", description="SQL"):
    conn.execute("""INSERT INTO job_postings VALUES
        (?, ?, 'Company', ?, ?, 'Seoul', NULL, 'Degree', 'Annual', '4000', '134',
         '2026-01-01', '2026-12-31', 'https://example.com', '2025-01-01T10:00:00')
    """, (posting_id, source, title, description))


class MigrationTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.addCleanup(self.conn.close)
        self.conn.executescript(LEGACY_SCHEMA)

    def migrate(self):
        self.conn.commit()
        with self.assertLogs("jobskillradar.migrations", level="WARNING") as logs:
            storage.ensure_schema(self.conn)
        return logs

    def test_all_legacy_fields_and_valid_skills_survive(self):
        legacy_posting(self.conn)
        self.conn.executemany("INSERT INTO posting_skills VALUES ('1', ?)", [("Python",), ("SQL",)])
        names = [r[1] for r in self.conn.execute("PRAGMA table_info(job_postings)")]
        before = dict(zip(names, self.conn.execute("SELECT * FROM job_postings").fetchone()))
        self.migrate()
        after = storage.load_postings(self.conn)[0]
        self.assertEqual(after, {k: v for k, v in before.items() if k != "created_at"})
        self.assertEqual(self.conn.execute("SELECT created_at FROM job_postings").fetchone()[0], before["created_at"])
        self.assertEqual(self.conn.execute("SELECT source, posting_id, skill FROM posting_skills ORDER BY skill").fetchall(),
                         [("work24", "1", "Python"), ("work24", "1", "SQL")])
        self.assertEqual(self.conn.execute("PRAGMA user_version").fetchone()[0], 4)
        self.assertEqual(self.conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)

    def test_multiple_postings_survive(self):
        for index in range(5):
            legacy_posting(self.conn, str(index))
        self.migrate()
        self.assertEqual(storage.count_postings(self.conn), 5)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM posting_skills").fetchone()[0], 10)

    def test_orphan_count_is_reported_and_no_parent_is_invented(self):
        legacy_posting(self.conn)
        self.conn.execute("INSERT INTO posting_skills VALUES ('missing', 'Java')")
        logs = self.migrate()
        self.assertIn("부모 없는 기술 1건", " ".join(logs.output))
        self.assertEqual(storage.count_postings(self.conn), 1)
        self.assertEqual(self.conn.execute("SELECT * FROM posting_skills WHERE posting_id='missing'").fetchall(), [])
        self.assertEqual(self.conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_stale_skills_reconciled_from_preserved_content(self):
        legacy_posting(self.conn)
        self.conn.executemany("INSERT INTO posting_skills VALUES ('1', ?)", [("Python",), ("Java",)])
        logs = self.migrate()
        self.assertIn("본문 불일치 기술 1건 제거", " ".join(logs.output))
        self.assertIn("누락 기술 1건 복원", " ".join(logs.output))
        self.assertEqual(self.conn.execute("SELECT skill FROM posting_skills ORDER BY skill").fetchall(), [("Python",), ("SQL",)])

    def test_initialization_is_idempotent(self):
        legacy_posting(self.conn)
        self.migrate()
        before = list(self.conn.iterdump())
        storage.ensure_schema(self.conn)
        storage.ensure_schema(self.conn)
        self.assertEqual(list(self.conn.iterdump()), before)

    def test_failure_after_copy_and_rename_rolls_back_schema_data_and_version(self):
        legacy_posting(self.conn)
        self.conn.commit()
        before = list(self.conn.iterdump())
        migrate = migrations._migrate_legacy
        def fail_after_copy(conn):
            migrate(conn)
            raise RuntimeError("injected after rename")
        with patch.object(migrations, "_migrate_legacy", side_effect=fail_after_copy):
            with self.assertRaisesRegex(RuntimeError, "injected"):
                storage.ensure_schema(self.conn)
        self.assertEqual(self.conn.execute("PRAGMA user_version").fetchone()[0], 0)
        self.assertEqual(list(self.conn.iterdump()), before)
        self.migrate()
        self.assertEqual(storage.count_postings(self.conn), 1)

    def test_invalid_legacy_identity_aborts_without_discarding_posting(self):
        legacy_posting(self.conn, source=" ")
        self.conn.commit()
        before = list(self.conn.iterdump())
        with self.assertRaises(ValueError):
            storage.ensure_schema(self.conn)
        self.assertEqual(list(self.conn.iterdump()), before)
        self.assertEqual(self.conn.execute("PRAGMA user_version").fetchone()[0], 0)

    def test_unknown_version_and_unknown_layout_are_rejected(self):
        self.conn.execute("PRAGMA user_version=99")
        with self.assertRaisesRegex(RuntimeError, "version"):
            storage.ensure_schema(self.conn)
        self.conn.execute("PRAGMA user_version=0")
        self.conn.execute("ALTER TABLE job_postings ADD COLUMN custom TEXT")
        with self.assertRaisesRegex(RuntimeError, "layout"):
            storage.ensure_schema(self.conn)
        self.assertIn("custom", [r[1] for r in self.conn.execute("PRAGMA table_info(job_postings)")])

    def test_uncommitted_legacy_transaction_is_not_committed_by_migration(self):
        legacy_posting(self.conn)
        with self.assertRaises(RuntimeError):
            storage.ensure_schema(self.conn)
        self.assertTrue(self.conn.in_transaction)
        self.conn.rollback()
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM job_postings").fetchone()[0], 0)

    def test_file_migration_backup_reopen_and_subsequent_upsert(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "legacy.sqlite"
            conn = sqlite3.connect(path)
            conn.executescript(LEGACY_SCHEMA)
            legacy_posting(conn)
            conn.execute("INSERT INTO posting_skills VALUES ('orphan', 'Java')")
            conn.commit()
            original = list(conn.iterdump())
            conn.close()
            with self.assertLogs("jobskillradar.migrations", level="WARNING"):
                self.assertEqual(len(storage.load_postings_from_db(path)), 1)
            backups = list(Path(tmp).glob('*.bak'))
            self.assertEqual(len(backups), 1)
            self.assertTrue(backups[0].name.startswith("legacy.sqlite.pre-v4-from-v0-"))
            backup = sqlite3.connect(backups[0])
            try:
                self.assertEqual(list(backup.iterdump()), original)
                self.assertEqual(backup.execute("PRAGMA user_version").fetchone()[0], 0)
            finally:
                backup.close()
            conn = storage.connect(path)
            try:
                self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)
                self.assertEqual(storage.save_postings(conn, [{"source": "work24", "posting_id": "1", "title": "Java"}]), 0)
                self.assertEqual(storage.load_postings(conn)[0]["title"], "Java")
                self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
            finally:
                conn.close()
            self.assertEqual(len(list(Path(tmp).glob('*.bak'))), 1)
            restored = Path(tmp) / "restored.sqlite"
            shutil.copy2(backups[0], restored)
            with self.assertLogs("jobskillradar.migrations", level="WARNING"):
                self.assertEqual(storage.load_postings_from_db(restored)[0]["title"], "Python")

    def test_backup_failure_prevents_any_migration(self):
        legacy_posting(self.conn)
        self.conn.commit()
        before = list(self.conn.iterdump())
        with patch.object(migrations, "_backup_database", side_effect=OSError("backup unavailable")):
            with self.assertRaisesRegex(OSError, "backup unavailable"):
                storage.ensure_schema(self.conn)
        self.assertEqual(list(self.conn.iterdump()), before)
        self.assertEqual(self.conn.execute("PRAGMA user_version").fetchone()[0], 0)

    def test_custom_legacy_objects_are_not_silently_dropped(self):
        self.conn.execute("CREATE INDEX custom_title ON job_postings(title)")
        with self.assertRaisesRegex(RuntimeError, "Custom"):
            storage.ensure_schema(self.conn)
        self.assertIsNotNone(self.conn.execute("SELECT name FROM sqlite_master WHERE name='custom_title'").fetchone())

    def test_fresh_memory_database_has_current_schema_and_constraints(self):
        fresh = sqlite3.connect(":memory:")
        try:
            storage.ensure_schema(fresh)
            self.assertEqual(fresh.execute("PRAGMA user_version").fetchone()[0], 4)
            self.assertEqual(fresh.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual(storage.save_postings(fresh, [{"source": "test", "posting_id": "1", "title": "SQL"}]), 1)
            self.assertEqual(storage.load_postings(fresh)[0]["title"], "SQL")
            self.assertEqual(fresh.execute("PRAGMA foreign_key_check").fetchall(), [])
        finally:
            fresh.close()


class DetailMigrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "v1.sqlite"
        self.conn = sqlite3.connect(self.path)
        self.addCleanup(self.conn.close)
        self.conn.executescript((Path(__file__).parent / "fixtures" / "v1_schema.sql").read_text())
        self.conn.executemany("""INSERT INTO job_postings
            (source, posting_id, title, description, career, created_at)
            VALUES (?, '1', 'Python', 'SQL', '무관', '2000-01-01T00:00:00')""", [("work24",), ("other",)])
        # Even stale/manual v1 skills must survive this additive migration exactly.
        self.conn.executemany("INSERT INTO posting_skills VALUES (?, '1', ?)",
                              [("work24", "Legacy manual skill"), ("other", "Java")])
        self.conn.commit()

    def snapshot(self):
        return {name: self.conn.execute(f"SELECT * FROM {name} ORDER BY source, posting_id").fetchall()
                for name in ("job_postings", "posting_skills")}

    def test_v1_upgrade_is_additive_preserving_every_row_and_custom_objects(self):
        before = self.snapshot()
        schema = self.conn.execute("SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        # Any attempt to rewrite existing postings/skills would fail this migration.
        for table in ("job_postings", "posting_skills"):
            for action in ("INSERT", "UPDATE", "DELETE"):
                self.conn.execute(f"""CREATE TRIGGER guard_{table}_{action} BEFORE {action} ON {table}
                    BEGIN SELECT RAISE(ABORT, 'Existing rows must not be rewritten'); END""")
        storage.ensure_schema(self.conn)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.conn.execute("PRAGMA user_version").fetchone()[0], 4)
        self.assertEqual(self.conn.execute("PRAGMA foreign_key_check").fetchall(), [])
        for name, sql in schema:
            self.assertEqual(self.conn.execute("SELECT sql FROM sqlite_master WHERE name=?", (name,)).fetchone()[0], sql)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM posting_details").fetchone()[0], 0)

    def test_v1_backup_is_recoverable_and_current_reopen_creates_no_backup(self):
        before = list(self.conn.iterdump())
        storage.ensure_schema(self.conn)
        backups = list(Path(self.tmp.name).glob("v1.sqlite.pre-v4-from-v1-*.bak"))
        self.assertEqual(len(backups), 1)
        backup_bytes = backups[0].read_bytes()
        backup = sqlite3.connect(backups[0])
        try:
            self.assertEqual(list(backup.iterdump()), before)
            self.assertEqual(backup.execute("PRAGMA user_version").fetchone()[0], 1)
            self.assertEqual(backup.execute("PRAGMA integrity_check").fetchall(), [("ok",)])
        finally:
            backup.close()
        current = list(self.conn.iterdump())
        storage.load_postings_from_db(self.path)
        self.assertEqual(list(self.conn.iterdump()), current)
        self.assertEqual(list(Path(self.tmp.name).glob("*.bak")), backups)
        restored = Path(self.tmp.name) / "restored.sqlite"
        shutil.copy2(backups[0], restored)
        self.assertEqual(len(storage.load_postings_from_db(restored)), 2)
        self.assertEqual(backups[0].read_bytes(), backup_bytes)

    def test_v1_failure_after_detail_ddl_rolls_back_and_retry_keeps_both_backups(self):
        before = list(self.conn.iterdump())
        create = migrations._create_detail_table
        def fail(conn):
            create(conn)
            raise RuntimeError("injected after detail DDL")
        with patch.object(migrations, "_create_detail_table", side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, "injected"):
                storage.ensure_schema(self.conn)
        self.assertEqual(list(self.conn.iterdump()), before)
        self.assertEqual(self.conn.execute("PRAGMA user_version").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("PRAGMA foreign_key_check").fetchall(), [])
        first = next(Path(self.tmp.name).glob("*.bak"))
        first_bytes = first.read_bytes()
        storage.ensure_schema(self.conn)
        self.assertEqual(len(list(Path(self.tmp.name).glob("*.bak"))), 2)
        self.assertEqual(first.read_bytes(), first_bytes)

    def test_actual_backup_failure_aborts_before_ddl_and_removes_incomplete_backup(self):
        before = list(self.conn.iterdump())
        with patch.object(migrations.sqlite3, "connect", side_effect=OSError("backup unavailable")):
            with self.assertRaises(OSError):
                storage.ensure_schema(self.conn)
        self.assertEqual(list(self.conn.iterdump()), before)
        self.assertEqual(self.conn.execute("PRAGMA user_version").fetchone()[0], 1)
        self.assertEqual(list(Path(self.tmp.name).glob("*.bak")), [])

    def test_v0_failure_in_final_v2_step_restores_original_legacy_database(self):
        legacy = sqlite3.connect(":memory:")
        self.addCleanup(legacy.close)
        legacy.executescript(LEGACY_SCHEMA)
        legacy_posting(legacy)
        legacy.commit()
        before = list(legacy.iterdump())
        with patch.object(migrations, "_create_detail_table", side_effect=RuntimeError("injected")):
            with self.assertRaises(RuntimeError):
                storage.ensure_schema(legacy)
        self.assertEqual(list(legacy.iterdump()), before)
        self.assertEqual(legacy.execute("PRAGMA user_version").fetchone()[0], 0)

    def test_fresh_file_and_current_reopen_have_detail_keys_without_backups(self):
        path = Path(self.tmp.name) / "fresh.sqlite"
        self.assertEqual(storage.load_postings_from_db(path), [])
        conn = storage.connect(path)
        self.addCleanup(conn.close)
        self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 4)
        columns = conn.execute("PRAGMA table_info(posting_details)").fetchall()
        self.assertEqual({row[1]: row[5] for row in columns if row[5]}, {"source": 1, "posting_id": 2})
        before = list(conn.iterdump())
        storage.ensure_schema(conn)
        self.assertEqual(list(conn.iterdump()), before)
        self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertEqual(list(Path(self.tmp.name).glob("*.bak")), [])


if __name__ == "__main__":
    unittest.main()
