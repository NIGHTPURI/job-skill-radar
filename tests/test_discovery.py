import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from jobskillradar import discovery, storage
from jobskillradar.discovery_pipeline import discover_work24_jobs
from jobskillradar.pipeline import save_profile
from jobskillradar.profile import TARGET_ROLES
from jobskillradar.role_classifier import BACKEND, FRONTEND
from jobskillradar.work24_client import Work24Error
from test_posting_details import detail


def posting(pid, **changes):
    return {'source': 'work24', 'posting_id': pid, 'title': '백엔드 개발자', **changes}


class DiscoveryPlanTest(unittest.TestCase):
    def test_role_plan_is_bounded_deterministic_and_independent_of_owned_skills(self):
        one = discovery.build_discovery_plan({'target_roles': [BACKEND], 'owned_skills': ['Java']})
        self.assertEqual([q['keyword'] for q in one['queries']], ['백엔드', '서버 개발'])
        self.assertEqual(one, discovery.build_discovery_plan({'target_roles': [BACKEND], 'owned_skills': ['Python']}))
        all_roles = discovery.build_discovery_plan({'target_roles': list(TARGET_ROLES) * 2})
        self.assertEqual(all_roles, discovery.build_discovery_plan({'target_roles': list(reversed(TARGET_ROLES))}))
        self.assertEqual(len(all_roles['queries']), discovery.MAX_QUERIES)
        self.assertEqual(set(discovery.ROLE_QUERIES), set(TARGET_ROLES))

    def test_shared_query_is_deduplicated_with_both_roles(self):
        with patch.dict(discovery.ROLE_QUERIES, {FRONTEND: ('백엔드',)}):
            plan = discovery.build_discovery_plan({'target_roles': [FRONTEND, BACKEND]})
        self.assertEqual(len(plan['queries']), 2)
        self.assertEqual(set(plan['queries'][0]['target_roles']), {FRONTEND, BACKEND})

    def test_missing_target_role_is_explicit_and_unknown_role_is_rejected(self):
        for profile in (None, {}, {'target_roles': []}):
            self.assertEqual(discovery.build_discovery_plan(profile)['status'], 'profile_needs_target_role')
        with self.assertRaises(ValueError):
            discovery.build_discovery_plan({'target_roles': ['Invented']})

    def test_budgets_reject_unbounded_and_invalid_values(self):
        for key, value in (('pages', 0), ('pages', 3), ('display', 51), ('max_details', 51),
                           ('max_details', -1), ('pages', True), ('max_details', 1.5)):
            values = {'pages': 1, 'display': 20, 'max_details': 20, key: value}
            with self.subTest(values=values), self.assertRaises(ValueError):
                discovery.validate_budget(**values)


class DiscoveryExecutionTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / 'radar.sqlite'
        save_profile(db_path=self.path, owned_skills=['Java'], target_roles=[BACKEND])
        blocker = patch('urllib.request.urlopen', side_effect=AssertionError('No real network'))
        blocker.start()
        self.addCleanup(blocker.stop)
        self.fetch = Mock(side_effect=lambda **kw: detail(posting_id=kw['wanted_auth_no']))

    def run_discovery(self, collector=None, **options):
        return discover_work24_jobs('secret-key', db_path=self.path,
            collector=collector or Mock(return_value=[posting('1')]), detail_fetcher=self.fetch, **options)

    def test_multi_query_dedupe_preserves_first_posting_and_all_query_provenance(self):
        result = self.run_discovery(Mock(side_effect=[[posting(' 1 ', title='First')] * 2,
                                                      [posting('1', title='Later'), posting('2')]]))
        self.assertEqual((len(result['postings']), result['new_postings'], result['details_saved']), (2, 2, 2))
        self.assertEqual(result['list_result_count'], 4)
        self.assertEqual(result['postings'][0]['queries'], ['백엔드', '서버 개발'])
        self.assertEqual(self.fetch.call_count, 2)
        self.assertEqual(next(p for p in storage.load_postings_from_db(self.path) if p['posting_id'] == '1')['title'], 'First')

    def test_partial_query_failure_keeps_other_results_and_safe_categories(self):
        result = self.run_discovery(Mock(side_effect=[OSError('authKey=secret-key raw response'), [posting('1')]]))
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['details_saved'], 1)
        self.assertEqual(result['query_failures'], [{'query': '백엔드', 'reason': 'transport_error'}])
        self.assertNotIn('secret-key', json.dumps(result))

    def test_all_query_failures_and_successful_empty_queries_are_different(self):
        failed = self.run_discovery(Mock(side_effect=Work24Error('api_error')))
        empty = self.run_discovery(Mock(return_value=[]))
        self.assertEqual(failed['status'], 'failed')
        self.assertEqual(empty['status'], 'completed')
        self.fetch.assert_not_called()

    def test_known_detail_reused_and_missing_detail_fetched(self):
        self.run_discovery()
        self.fetch.reset_mock()
        result = self.run_discovery(Mock(return_value=[posting('1'), posting('2')]))
        self.assertEqual((result['details_reused'], result['details_saved'], result['new_postings']), (1, 1, 1))
        self.fetch.assert_called_once_with(auth_key='secret-key', wanted_auth_no='2')

    def test_explicit_refresh_and_failure_preserve_old_detail(self):
        self.run_discovery()
        old = storage.load_posting_detail_from_db(self.path, 'work24', '1')
        self.fetch.side_effect = Work24Error('transport_error')
        result = self.run_discovery(refresh_existing_details=True)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(storage.load_posting_detail_from_db(self.path, 'work24', '1'), old)
        self.fetch.side_effect = lambda **kw: detail(posting_id='1', job_content='Changed')
        result = self.run_discovery(refresh_existing_details=True)
        self.assertEqual(result['details_saved'], 1)
        self.assertEqual(storage.load_posting_detail_from_db(self.path, 'work24', '1')['job_content'], 'Changed')

    def test_detail_cap_includes_failures_and_defers_without_fabrication(self):
        self.fetch.side_effect = Work24Error('api_error')
        result = self.run_discovery(Mock(return_value=[posting(str(i)) for i in range(4)]), max_details=2)
        self.assertEqual((self.fetch.call_count, result['details_deferred'], len(result['detail_failures'])), (2, 2, 2))
        self.assertEqual(len(storage.load_postings_from_db(self.path)), 4)

    def test_zero_detail_budget_and_new_before_known_refresh(self):
        self.run_discovery()
        self.fetch.reset_mock()
        result = self.run_discovery(Mock(return_value=[posting('1'), posting('2')]), max_details=1, refresh_existing_details=True)
        self.fetch.assert_called_once_with(auth_key='secret-key', wanted_auth_no='2')
        result = self.run_discovery(max_details=0)
        self.assertEqual(result['details_reused'], 1)

    def test_no_connection_or_write_transaction_across_http(self):
        opened = []
        original = storage.connect
        def connect(path):
            conn = original(path)
            opened.append(conn)
            return conn
        def assert_closed():
            for conn in opened:
                with self.assertRaises(sqlite3.ProgrammingError):
                    conn.execute('SELECT 1')
            with closing(sqlite3.connect(self.path, timeout=0)) as conn:
                conn.execute('BEGIN IMMEDIATE')
                conn.rollback()
        def collect(**kw):
            assert_closed()
            return [posting('1')]
        def fetch(**kw):
            assert_closed()
            return detail(posting_id='1')
        self.fetch.side_effect = fetch
        with patch.object(storage, 'connect', side_effect=connect):
            self.run_discovery(collect)
        assert_closed()

    def test_non_work24_and_missing_identity_are_not_admitted(self):
        for row in (posting('1', source='manual'), posting('')):
            with self.subTest(row=row):
                result = self.run_discovery(Mock(return_value=[row]))
                self.assertEqual(result['status'], 'failed')
                self.assertEqual(result['postings'], [])
        self.fetch.assert_not_called()

    def test_detail_identity_mismatch_is_partial_without_wrong_row(self):
        self.fetch.side_effect = lambda **kw: detail(posting_id='wrong')
        result = self.run_discovery()
        self.assertEqual(result['detail_failures'][0]['reason'], 'identity_mismatch')
        self.assertIsNone(storage.load_posting_detail_from_db(self.path, 'work24', '1'))

    def test_profile_or_key_missing_stops_before_requests(self):
        collector = Mock()
        with self.assertRaises(ValueError):
            discover_work24_jobs('', db_path=self.path, collector=collector)
        with self.assertRaises(ValueError):
            discover_work24_jobs('fake', db_path=self.path.parent / 'empty.sqlite', collector=collector)
        collector.assert_not_called()

    def test_storage_failure_rolls_back_entire_batch(self):
        with patch.object(storage, 'save_posting_details', side_effect=RuntimeError('injected')):
            with self.assertRaises(RuntimeError):
                self.run_discovery()
        self.assertEqual(storage.load_postings_from_db(self.path), [])

    def test_progress_is_explicit_and_parameters_are_bounded(self):
        progress = Mock()
        collector = Mock(return_value=[posting('1')])
        self.run_discovery(collector, progress=progress, pages=2, display=10)
        self.assertEqual([c.args[0] for c in progress.call_args_list], ['query', 'query', 'detail'])
        self.assertTrue(all(c.kwargs['pages'] == 2 and c.kwargs['display'] == 10 for c in collector.call_args_list))


if __name__ == '__main__':
    unittest.main()
