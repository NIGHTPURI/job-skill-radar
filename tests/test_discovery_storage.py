import copy
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from jobskillradar import discovery_storage, migrations, storage
from jobskillradar.discovery_pipeline import discover_work24_jobs
from jobskillradar.pipeline import save_profile
from jobskillradar.role_classifier import BACKEND
from jobskillradar.work24_client import Work24Error
from test_discovery import posting
from test_posting_details import detail


class DiscoveryPersistenceTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / 'radar.sqlite'
        save_profile(db_path=self.path, target_roles=[BACKEND], owned_skills=['Java'])
        blocker = patch('urllib.request.urlopen', side_effect=AssertionError('No network'))
        blocker.start()
        self.addCleanup(blocker.stop)

    def discover(self, count=10, collector=None, **options):
        return discover_work24_jobs('fake', db_path=self.path,
            collector=collector or Mock(return_value=[posting(str(i)) for i in range(count)]),
            detail_fetcher=lambda **kw: detail(posting_id=kw['wanted_auth_no']), **options)

    def test_first_second_third_run_newness_membership_and_latest_restart(self):
        first, second, third = self.discover(), self.discover(), self.discover(12)
        self.assertEqual([r['new_postings'] for r in (first, second, third)], [10, 0, 2])
        self.assertEqual([r['details_saved'] for r in (first, second, third)], [10, 0, 2])
        for result in (first, second, third):
            loaded = discovery_storage.load_discovery_run(self.path, result['run_id'])
            self.assertEqual({**loaded, 'postings': sorted(loaded['postings'], key=lambda m: m['posting_id'])},
                             {**result, 'postings': sorted(result['postings'], key=lambda m: m['posting_id'])})
        self.assertEqual(discovery_storage.load_discovery_run(self.path)['run_id'], third['run_id'])
        self.assertEqual(len(discovery_storage.list_discovery_runs(self.path)), 3)
        with closing(storage.connect(self.path)) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM job_postings').fetchone()[0], 12)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM discovery_run_postings').fetchone()[0], 32)

    def test_partial_failed_empty_and_profile_revision_are_persisted(self):
        partial = self.discover(collector=Mock(side_effect=[[posting('1')], Work24Error('api_error')]))
        failed = self.discover(collector=Mock(side_effect=OSError('authKey=never-store-this')))
        save_profile(db_path=self.path, target_roles=[BACKEND], owned_skills=['Kotlin'])
        empty = self.discover(0)
        self.assertEqual([r['status'] for r in (partial, failed, empty)], ['partial', 'failed', 'completed'])
        self.assertEqual(empty['profile_revision'], 2)
        for r in (partial, failed, empty):
            self.assertEqual(discovery_storage.load_discovery_run(self.path, r['run_id']), r)
        self.assertNotIn(b'never-store-this', self.path.read_bytes())

    def test_membership_write_failure_rolls_back_postings_details_and_run(self):
        with closing(storage.connect(self.path)) as conn:
            conn.execute("CREATE TRIGGER reject_members BEFORE INSERT ON discovery_run_postings BEGIN SELECT RAISE(ABORT, 'injected'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.discover()
        self.assertEqual(storage.load_postings_from_db(self.path), [])
        self.assertIsNone(discovery_storage.load_discovery_run(self.path))

    def test_newness_checked_at_save_not_before_network(self):
        def concurrent_insert(**kw):
            storage.save_postings_to_db(self.path, [posting('1')])
            return [posting('1')]
        result = self.discover(collector=concurrent_insert)
        self.assertEqual(result['new_postings'], 0)

    def test_membership_fk_restricts_posting_delete_run_delete_cascades(self):
        result = self.discover(1)
        with closing(storage.connect(self.path)) as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("DELETE FROM job_postings WHERE source='work24'")
            conn.rollback()
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO discovery_run_postings VALUES ('missing', 'work24', '0', 0, '[]')")
            conn.rollback()
            conn.execute('DELETE FROM discovery_runs WHERE run_id=?', (result['run_id'],))
            conn.commit()
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM discovery_run_postings').fetchone()[0], 0)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM job_postings').fetchone()[0], 1)

    def test_manual_identity_is_not_known_work24_identity(self):
        storage.save_postings_to_db(self.path, [posting('0', source='manual')])
        self.assertEqual(self.discover(1)['new_postings'], 1)

    def test_invalid_failure_payload_counts_timestamp_and_extra_fields_are_rejected(self):
        result = self.discover(1)
        mutations = [lambda r: r.update(auth_key='secret'),
                     lambda r: r.update(details_saved=99),
                     lambda r: r.update(completed_at='not a time'),
                     lambda r: r['postings'][0].update(queries=['authKey=secret']),
                     lambda r: r.update(query_successes=1, query_failures=[{'query': '서버 개발', 'reason': 'secret'}]),
                     lambda r: r.update(query_successes=1, query_failures=[{'query': '서버 개발', 'reason': 'api_error', 'body': 'secret'}])]
        for mutate in mutations:
            bad = copy.deepcopy(result)
            mutate(bad)
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                discovery_storage._validate_run(bad)

    def test_history_limit_and_missing_run(self):
        self.assertIsNone(discovery_storage.load_discovery_run(self.path))
        self.assertIsNone(discovery_storage.load_discovery_run(self.path, 'absent'))
        self.discover(0)
        self.assertEqual(len(discovery_storage.list_discovery_runs(self.path, limit=1)), 1)
        with self.assertRaises(ValueError):
            discovery_storage.list_discovery_runs(self.path, limit=0)


class DiscoveryMigrationTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / 'v3.sqlite'
        self.conn = sqlite3.connect(self.path)
        self.addCleanup(self.conn.close)
        self.conn.executescript((Path(__file__).parent / 'fixtures/v3_schema.sql').read_text())
        for source in ('manual', 'work24'):
            self.conn.execute("INSERT INTO job_postings(source,posting_id,title,created_at) VALUES (?, 'same', 'Java', '2000-01-01')", (source,))
            self.conn.execute("INSERT INTO posting_skills VALUES (?, 'same', 'Original skill')", (source,))
            self.conn.execute("INSERT INTO posting_details(source,posting_id,job_content,keywords,fetched_at) VALUES (?, 'same', 'Raw body', '[]', '2026-09-17T00:00:00Z')", (source,))
        self.conn.execute("INSERT INTO user_profile VALUES (1, 7, '[\"Java\"]', ?, '[\"서울\"]', '[\"부산\"]')", (json.dumps([BACKEND]),))
        self.conn.commit()

    def test_v3_additive_preservation_backup_recoverability_and_idempotence(self):
        tables = ('job_postings', 'posting_skills', 'posting_details', 'user_profile')
        before = {t: self.conn.execute(f'SELECT * FROM {t}').fetchall() for t in tables}
        old_dump = list(self.conn.iterdump())
        for table in tables:
            for action in ('INSERT', 'UPDATE', 'DELETE'):
                self.conn.execute(f"CREATE TRIGGER guard_{table}_{action} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'no rewriting'); END")
        migrations.ensure_schema(self.conn)
        self.assertEqual({t: self.conn.execute(f'SELECT * FROM {t}').fetchall() for t in tables}, before)
        self.assertEqual(self.conn.execute('PRAGMA user_version').fetchone()[0], 4)
        self.assertEqual(self.conn.execute('PRAGMA foreign_key_check').fetchall(), [])
        backup, = self.path.parent.glob('*.pre-v4-from-v3-*.bak')
        with closing(sqlite3.connect(backup)) as restored:
            self.assertEqual(restored.execute('PRAGMA user_version').fetchone()[0], 3)
            self.assertEqual({t: restored.execute(f'SELECT * FROM {t}').fetchall() for t in tables}, before)
            self.assertEqual(restored.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        saved = backup.read_bytes()
        migrations.ensure_schema(self.conn)
        self.assertEqual(backup.read_bytes(), saved)
        self.assertEqual(len(list(self.path.parent.glob('*.bak'))), 1)

    def test_v0_v1_v2_v3_final_ddl_failure_rolls_back_then_recovers(self):
        for version, filename in ((0, 'legacy_schema.sql'), (1, 'v1_schema.sql'), (2, 'v2_schema.sql'), (3, 'v3_schema.sql')):
            with self.subTest(version=version), closing(sqlite3.connect(':memory:')) as conn:
                conn.executescript((Path(__file__).parent / 'fixtures' / filename).read_text())
                conn.execute("INSERT INTO job_postings(source,posting_id,created_at) VALUES ('work24','one','2000-01-01')")
                conn.commit()
                before = list(conn.iterdump())
                original = migrations._create_discovery_tables
                def fail(connection):
                    original(connection)
                    raise RuntimeError('after discovery DDL')
                with patch.object(migrations, '_create_discovery_tables', side_effect=fail), self.assertRaises(RuntimeError):
                    migrations.ensure_schema(conn)
                self.assertEqual(list(conn.iterdump()), before)
                self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], version)
                migrations.ensure_schema(conn)
                self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 4)
                self.assertEqual(conn.execute('SELECT created_at FROM job_postings').fetchone()[0], '2000-01-01')

    def test_backup_failure_aborts_and_retry_does_not_overwrite(self):
        before = list(self.conn.iterdump())
        with patch.object(migrations.sqlite3, 'connect', side_effect=OSError('injected')), self.assertRaises(OSError):
            migrations.ensure_schema(self.conn)
        self.assertEqual(list(self.conn.iterdump()), before)
        self.assertEqual(list(self.path.parent.glob('*.bak')), [])
        with patch.object(migrations, '_create_discovery_tables', side_effect=RuntimeError('injected')), self.assertRaises(RuntimeError):
            migrations.ensure_schema(self.conn)
        backup, = self.path.parent.glob('*.bak')
        saved = backup.read_bytes()
        migrations.ensure_schema(self.conn)
        self.assertEqual(backup.read_bytes(), saved)
        self.assertEqual(len(list(self.path.parent.glob('*.bak'))), 2)

    def test_fresh_current_has_no_backup_and_unknown_old_tables_are_rejected(self):
        with closing(storage.connect(self.path.parent / 'fresh.sqlite')) as conn:
            migrations.ensure_schema(conn)
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 4)
            migrations.ensure_schema(conn)
        self.assertEqual(list(self.path.parent.glob('*.bak')), [])
        self.conn.execute('CREATE TABLE discovery_runs (custom TEXT)')
        self.conn.commit()
        before = list(self.conn.iterdump())
        with self.assertRaises(RuntimeError):
            migrations.ensure_schema(self.conn)
        self.assertEqual(list(self.conn.iterdump()), before)


if __name__ == '__main__':
    unittest.main()
