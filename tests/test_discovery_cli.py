import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from jobskillradar import config
from jobskillradar.pipeline import save_profile
from jobskillradar.role_classifier import BACKEND
from jobskillradar.work24_client import Work24Error
from test_discovery import posting
from test_discovery_acceptance import clean_detail

spec = importlib.util.spec_from_file_location('discover_jobs_cli', ROOT / 'scripts/discover_jobs.py')
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


class DiscoveryCliTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / 'cli.sqlite'
        save_profile(db_path=self.path, owned_skills=['Java'], target_roles=[BACKEND])
        for context in (patch.dict(os.environ, {'WORK24_AUTH_KEY': 'secret-key'}),
                        patch.object(config, '_ENV_LOADED', True),
                        patch('urllib.request.urlopen', side_effect=AssertionError('No network'))):
            context.start()
            self.addCleanup(context.stop)

    def run_cli(self, *args, collector=None, fetcher=None):
        output, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            code = cli.main(['--db-path', str(self.path), *args],
                collector=collector or Mock(return_value=[posting('1')]),
                detail_fetcher=fetcher or (lambda **kw: clean_detail(kw['wanted_auth_no'])))
        self.assertNotIn('secret-key', output.getvalue() + error.getvalue())
        return code, output.getvalue(), error.getvalue()

    def test_success_json_is_scheduler_friendly_and_second_run_reuses_detail(self):
        code, output, _ = self.run_cli('--json')
        result = json.loads(output)
        self.assertEqual((code, result['status'], result['new_postings']), (0, 'completed', 1))
        fetch = Mock(side_effect=AssertionError('Should reuse'))
        code, output, _ = self.run_cli('--json', fetcher=fetch)
        self.assertEqual(json.loads(output)['details_reused'], 1)
        fetch.assert_not_called()

    def test_partial_and_total_failure_exit_codes_and_safe_json(self):
        code, output, _ = self.run_cli('--json', collector=Mock(side_effect=[[posting('1')], Work24Error('api_error')]))
        self.assertEqual((code, json.loads(output)['status']), (2, 'partial'))
        code, output, _ = self.run_cli('--json', collector=Mock(side_effect=OSError('authKey=secret-key')))
        self.assertEqual((code, json.loads(output)['status']), (1, 'failed'))

    def test_missing_key_and_profile_exit_one_before_network(self):
        collector = Mock()
        with patch.dict(os.environ, {'WORK24_AUTH_KEY': ''}):
            self.assertEqual(self.run_cli(collector=collector)[0], 1)
        self.path = self.path.parent / 'empty.sqlite'
        self.assertEqual(self.run_cli(collector=collector)[0], 1)
        collector.assert_not_called()

    def test_invalid_arguments_and_unexpected_exception_are_safe_exit_one(self):
        for args in (('--pages', '3'), ('--max-details', '-1'), ('--pages', 'secret-key'), ('--unknown', 'secret-key')):
            self.assertEqual(self.run_cli(*args)[0], 1)
        code, output, error = self.run_cli(collector=Mock(side_effect=RuntimeError('secret-key')))
        self.assertEqual(code, 1)
        self.assertTrue(error)

    def test_explicit_refresh_and_detail_budget_flags(self):
        self.run_cli()
        fetch = Mock(side_effect=lambda **kw: clean_detail(kw['wanted_auth_no']))
        code, output, _ = self.run_cli('--refresh-existing-details', '--max-details', '1', fetcher=fetch)
        self.assertEqual(code, 0)
        fetch.assert_called_once()
        self.assertIn('상세 성공 1', output)

    def test_zero_detail_budget_remains_successful_list_run(self):
        code, output, _ = self.run_cli('--max-details', '0', '--json')
        self.assertEqual((code, json.loads(output)['details_deferred']), (0, 1))
