import shutil
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from jobskillradar import migrations, storage
from jobskillradar.profile_storage import load_profile_from_db

FIXTURES = Path(__file__).parent / 'fixtures'


class ProfileMigrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'v2.sqlite'
        self.conn = sqlite3.connect(self.path)
        self.addCleanup(self.conn.close)
        self.conn.executescript((FIXTURES / 'v2_schema.sql').read_text())
        for source in ('manual', 'work24'):
            self.conn.execute("INSERT INTO job_postings(source,posting_id,title,created_at) VALUES (?, 'same', 'Java', '2000-01-01')", (source,))
            self.conn.execute("INSERT INTO posting_skills VALUES (?, 'same', 'Existing custom skill')", (source,))
            self.conn.execute("INSERT INTO posting_details(source,posting_id,job_content,keywords,fetched_at) VALUES (?, 'same', '  Java or Kotlin required\n', '[\"k8s\"]', '2026-09-17T00:00:00Z')", (source,))
        self.conn.commit()

    def snapshot(self):
        return {name: self.conn.execute(f'SELECT * FROM {name} ORDER BY source, posting_id').fetchall()
                for name in ('job_postings', 'posting_skills', 'posting_details')}

    def test_v2_upgrade_does_not_rewrite_any_posting_table_and_preserves_fk(self):
        before = self.snapshot()
        schemas = self.conn.execute("SELECT name, sql FROM sqlite_master WHERE type='table'").fetchall()
        for table in before:
            for action in ('INSERT', 'UPDATE', 'DELETE'):
                self.conn.execute(f"CREATE TRIGGER guard_{table}_{action} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'no rewriting'); END")
        migrations.ensure_schema(self.conn)
        self.assertEqual(self.snapshot(), before)
        for name, sql in schemas:
            self.assertEqual(self.conn.execute('SELECT sql FROM sqlite_master WHERE name=?', (name,)).fetchone()[0], sql)
        self.assertEqual(self.conn.execute('PRAGMA user_version').fetchone()[0], 4)
        self.assertEqual(self.conn.execute('PRAGMA foreign_key_check').fetchall(), [])
        self.assertEqual(self.conn.execute('SELECT * FROM user_profile').fetchall(), [])

    def test_v2_backup_restores_exact_source_and_current_reopen_is_idempotent(self):
        old = list(self.conn.iterdump())
        migrations.ensure_schema(self.conn)
        backup, = Path(self.tmp.name).glob('v2.sqlite.pre-v4-from-v2-*.bak')
        with closing(sqlite3.connect(backup)) as conn:
            self.assertEqual(list(conn.iterdump()), old)
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 2)
            self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        before = list(self.conn.iterdump())
        content = backup.read_bytes()
        self.assertIsNone(load_profile_from_db(self.path))
        self.assertEqual(list(self.conn.iterdump()), before)
        self.assertEqual(len(list(Path(self.tmp.name).glob('*.bak'))), 1)
        restored = Path(self.tmp.name) / 'restored.sqlite'
        shutil.copy2(backup, restored)
        self.assertEqual(len(storage.load_postings_from_db(restored)), 2)
        self.assertEqual(backup.read_bytes(), content)

    def test_final_profile_ddl_failure_rolls_back_v0_v1_and_v2(self):
        for version, fixture in ((0, 'legacy_schema.sql'), (1, 'v1_schema.sql'), (2, 'v2_schema.sql')):
            with self.subTest(version=version), closing(sqlite3.connect(':memory:')) as conn:
                conn.executescript((FIXTURES / fixture).read_text())
                conn.execute("INSERT INTO job_postings(source,posting_id,title,created_at) VALUES ('work24','one','Java','2000-01-01')")
                conn.commit()
                before = list(conn.iterdump())
                original = migrations._create_profile_table
                def fail(connection):
                    original(connection)
                    raise RuntimeError('injected after profile DDL')
                with patch.object(migrations, '_create_profile_table', side_effect=fail), self.assertRaises(RuntimeError):
                    migrations.ensure_schema(conn)
                self.assertEqual(list(conn.iterdump()), before)
                self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], version)
                migrations.ensure_schema(conn)
                self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 4)
                self.assertEqual(conn.execute('SELECT created_at FROM job_postings').fetchone()[0], '2000-01-01')

    def test_backup_failure_aborts_v2_upgrade_without_changes(self):
        before = list(self.conn.iterdump())
        with patch.object(migrations.sqlite3, 'connect', side_effect=OSError('backup unavailable')):
            with self.assertRaises(OSError):
                migrations.ensure_schema(self.conn)
        self.assertEqual(list(self.conn.iterdump()), before)
        self.assertEqual(self.conn.execute('PRAGMA user_version').fetchone()[0], 2)
        self.assertEqual(list(Path(self.tmp.name).glob('*.bak')), [])

    def test_retry_does_not_overwrite_preexisting_backup(self):
        with patch.object(migrations, '_create_profile_table', side_effect=RuntimeError('injected')):
            with self.assertRaises(RuntimeError):
                migrations.ensure_schema(self.conn)
        old, = Path(self.tmp.name).glob('*.bak')
        data = old.read_bytes()
        migrations.ensure_schema(self.conn)
        self.assertEqual(len(list(Path(self.tmp.name).glob('*.bak'))), 2)
        self.assertEqual(old.read_bytes(), data)

    def test_unexpected_profile_table_in_v2_is_not_overwritten(self):
        self.conn.execute('CREATE TABLE user_profile (custom TEXT)')
        self.conn.commit()
        before = list(self.conn.iterdump())
        with self.assertRaisesRegex(RuntimeError, 'Unexpected user_profile'):
            migrations.ensure_schema(self.conn)
        self.assertEqual(list(self.conn.iterdump()), before)
        self.assertEqual(list(Path(self.tmp.name).glob('*.bak')), [])

    def test_fresh_database_has_profile_table_without_backup(self):
        path = Path(self.tmp.name) / 'fresh.sqlite'
        self.assertIsNone(load_profile_from_db(path))
        with closing(sqlite3.connect(path)) as conn:
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 4)
            self.assertEqual(conn.execute('SELECT * FROM user_profile').fetchall(), [])
        self.assertEqual(list(Path(self.tmp.name).glob('*.bak')), [])

    def test_v3_preserves_source_specific_cascade(self):
        migrations.ensure_schema(self.conn)
        self.conn.execute("DELETE FROM job_postings WHERE source='manual'")
        self.conn.commit()
        self.assertEqual(self.conn.execute('SELECT source FROM posting_details').fetchall(), [('work24',)])
        self.assertEqual(self.conn.execute('SELECT source FROM posting_skills').fetchall(), [('work24',)])
        self.assertEqual(self.conn.execute('PRAGMA foreign_key_check').fetchall(), [])


if __name__ == '__main__':
    unittest.main()
