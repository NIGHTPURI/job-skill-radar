import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from jobskillradar import pipeline, profile_storage, storage
from jobskillradar.role_classifier import BACKEND
from jobskillradar.work24_client import Work24Error
from test_requirement_extractor import source_detail


class ComparisonPipelineTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / 'compare.sqlite'
        blocker = patch('urllib.request.urlopen', side_effect=AssertionError('Unexpected HTTP'))
        blocker.start()
        self.addCleanup(blocker.stop)

    def save_profile(self, skills):
        return pipeline.save_profile(db_path=self.path, owned_skills=skills, target_roles=[BACKEND])

    def manual(self):
        return pipeline.create_manual_posting(db_path=self.path, company='Example', title='Backend Engineer', body='Java or Kotlin required')

    def compare(self, source, identity):
        return pipeline.load_posting_comparison(source, identity, db_path=self.path)

    def dump(self):
        with closing(storage.connect(self.path)) as conn:
            return list(conn.iterdump())

    def test_restart_manual_comparison_and_profile_revision_reprocessing(self):
        identity = self.manual()
        self.save_profile(['Kotlin'])
        before = self.dump()
        first = self.compare('manual', identity)
        self.assertEqual(first['groups'][0]['status'], 'satisfied')
        self.assertEqual(first['required'], [])
        self.assertEqual(first['role_alignment'], 'target_role')
        self.assertEqual(first, self.compare('manual', identity))
        self.assertEqual(self.dump(), before)
        self.save_profile([])
        latest = self.compare('manual', identity)
        self.assertEqual(latest['profile_revision'], 2)
        self.assertEqual(latest['groups'][0]['status'], 'not_satisfied_from_profile')
        self.assertEqual(first['groups'][0]['status'], 'satisfied')

    def test_body_edit_uses_latest_requirements_without_stale_comparison(self):
        identity = self.manual()
        self.save_profile(['Java'])
        first = self.compare('manual', identity)
        pipeline.update_manual_posting('manual', identity, db_path=self.path, company='Example', title='Backend Engineer', body='Python required')
        latest = self.compare('manual', identity)
        self.assertEqual(latest['groups'], [])
        self.assertEqual([(s['skill'], s['status']) for s in latest['required']], [('Python', 'profile_missing')])
        self.assertEqual(first['groups'][0]['relation'], 'any_of')

    def test_work24_flow_and_failed_refresh_preserve_comparison_evidence(self):
        self.save_profile(['springboot'])
        posting = {'source': 'work24', 'posting_id': 'synthetic', 'title': 'Backend Engineer'}
        storage.save_postings_to_db(self.path, [posting])
        missing = self.compare('work24', 'synthetic')
        self.assertEqual(missing['quality_status'], 'detail_not_fetched')
        storage.save_posting_details_to_db(self.path, [source_detail(job_content='Spring Boot required')])
        old = self.compare('work24', 'synthetic')
        self.assertEqual(old['required'][0]['status'], 'matched')
        outcome = pipeline.collect_work24_with_details_to_db('fake', ['backend'], db_path=self.path,
            collector=Mock(return_value=[posting]), detail_fetcher=Mock(side_effect=Work24Error('transport_error')))
        self.assertEqual(len(outcome['detail_failures']), 1)
        self.assertEqual(self.compare('work24', 'synthetic'), old)

    def test_missing_profile_and_posting_are_visible_errors(self):
        identity = self.manual()
        with self.assertRaisesRegex(ValueError, 'Save a local profile'):
            self.compare('manual', identity)
        self.save_profile([])
        with self.assertRaisesRegex(ValueError, 'does not exist'):
            self.compare('manual', 'missing')

    def test_readers_close_before_matcher_and_failure_preserves_all_data(self):
        identity = self.manual()
        self.save_profile(['Java'])
        before = self.dump()
        profile_conn, posting_conn = storage.connect(self.path), storage.connect(self.path)
        original = pipeline.compare_profile_to_requirements
        def check(*args, **kwargs):
            for conn in (profile_conn, posting_conn):
                with self.assertRaises(sqlite3.ProgrammingError):
                    conn.execute('SELECT 1')
            return original(*args, **kwargs)
        with patch.object(profile_storage, 'connect', return_value=profile_conn), \
                patch.object(storage, 'connect', return_value=posting_conn), \
                patch.object(pipeline, 'compare_profile_to_requirements', side_effect=check):
            self.compare('manual', identity)
        with patch.object(pipeline, 'compare_profile_to_requirements', side_effect=RuntimeError('injected')):
            with self.assertRaises(RuntimeError):
                self.compare('manual', identity)
        self.assertEqual(self.dump(), before)

    def test_comparison_does_not_change_market_analysis_or_schema(self):
        identity = self.manual()
        self.save_profile(['Kotlin'])
        storage.save_postings_to_db(self.path, [{'source': 'work24', 'posting_id': 'w', 'title': 'SQL'}])
        before = pipeline.load_market_analysis('DB 우선', db_path=self.path)
        self.compare('manual', identity)
        self.assertEqual(pipeline.load_market_analysis('DB 우선', db_path=self.path), before)
        with closing(storage.connect(self.path)) as conn:
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 4)
            self.assertEqual(conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall(),
                             [('discovery_run_postings',), ('discovery_runs',), ('job_postings',), ('posting_details',), ('posting_skills',), ('user_profile',)])


if __name__ == '__main__':
    unittest.main()
