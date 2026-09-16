import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from jobskillradar import storage
from jobskillradar.discovery_pipeline import discover_work24_jobs, load_discovery_shortlist
from jobskillradar.discovery_storage import load_discovery_run
from jobskillradar.pipeline import load_db_analysis, save_profile
from jobskillradar.role_classifier import BACKEND
from jobskillradar.work24_client import Work24Error
from test_discovery import posting
from test_posting_details import detail


def clean_detail(pid, body='Java required', **changes):
    return detail(posting_id=pid, job_content=body, preferred_conditions=None,
                  other_preferred_conditions=None, certificate=None, computer_skill=None,
                  other_information=None, keywords=[], **changes)


class DiscoveryAcceptanceTest(unittest.TestCase):
    def test_three_daily_runs_preserve_raw_dedupe_newness_groups_and_explanations(self):
        with tempfile.TemporaryDirectory() as tmp, patch('urllib.request.urlopen', side_effect=AssertionError('No network')):
            path = Path(tmp) / 'daily.sqlite'
            save_profile(db_path=path, target_roles=[BACKEND], owned_skills=['Java'])
            storage.save_postings_to_db(path, [posting('old'), posting('manual', source='manual', title='Invisible manual')])
            old = clean_detail('old', 'Java required', fetched_at='2026-09-01T00:00:00Z')
            storage.save_posting_details_to_db(path, [old])
            bodies = {'choice': 'Java or Kotlin required', 'gap': 'Kafka required', 'ready': 'Java required',
                      'missing': 'Python required', 'old': 'Java required'}
            calls, requests = [], []
            refresh = False
            def collect(**kw):
                requests.append(kw['keyword'])
                return [posting(pid) for pid in bodies] + [posting('choice')]
            def fetch(**kw):
                pid = kw['wanted_auth_no']
                calls.append(pid)
                if pid == 'missing' or (refresh and pid == 'old'):
                    raise Work24Error('transport_error')
                return clean_detail(pid, bodies[pid])
            first = discover_work24_jobs('fake', db_path=path, collector=collect, detail_fetcher=fetch, max_details=4)
            self.assertEqual((first['status'], len(first['postings']), first['new_postings']), ('partial', 5, 4))
            self.assertEqual((len(calls), len(set(calls))), (4, 4))
            self.assertNotIn('old', calls)
            view = load_discovery_shortlist(db_path=path)
            by_id = {i['posting']['posting_id']: i for i in view['items']}
            self.assertEqual(by_id['choice']['bucket'], 'review_first')
            self.assertEqual(by_id['choice']['comparison']['required'], [])
            self.assertEqual(by_id['choice']['comparison']['groups'][0]['status'], 'satisfied')
            self.assertEqual(by_id['gap']['bucket'], 'review_with_gaps')
            self.assertIn({'code': 'required_not_listed', 'values': ['Kafka']}, by_id['gap']['reasons'])
            self.assertEqual(by_id['ready']['bucket'], 'review_first')
            self.assertEqual(by_id['missing']['bucket'], 'needs_information')
            self.assertEqual(set(by_id), set(bodies))
            calls.clear()
            refresh = True
            second = discover_work24_jobs('fake', db_path=path, collector=collect, detail_fetcher=fetch,
                                           max_details=5, refresh_existing_details=True)
            self.assertEqual(second['new_postings'], 0)
            self.assertEqual(storage.load_posting_detail_from_db(path, 'work24', 'old'), old)
            self.assertEqual(len(calls), 5)
            bodies['new'] = 'SQL required'
            calls.clear()
            third = discover_work24_jobs('fake', db_path=path, collector=collect, detail_fetcher=fetch)
            self.assertEqual(third['new_postings'], 1)
            self.assertEqual(calls, ['new', 'missing'])
            self.assertEqual(len(requests), 6)
            self.assertEqual(load_discovery_run(path)['run_id'], third['run_id'])
            self.assertNotIn('manual', {p['source'] for p in load_db_analysis(db_path=path)['postings']})
            with closing(storage.connect(path)) as conn:
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM discovery_run_postings').fetchone()[0], 16)
                self.assertEqual(conn.execute('PRAGMA foreign_key_check').fetchall(), [])
