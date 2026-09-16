import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from jobskillradar import config
from jobskillradar.discovery_storage import list_discovery_runs
from jobskillradar.pipeline import save_profile
from jobskillradar.role_classifier import BACKEND
from jobskillradar.work24_client import Work24Error
from test_discovery import posting
from test_discovery_acceptance import clean_detail


class DiscoveryUiTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / 'ui.sqlite'
        self.collector = Mock(return_value=[posting('one', company='Example', url='https://example.com/jobs/one')])
        self.fetcher = Mock(side_effect=lambda **kw: clean_detail(kw['wanted_auth_no'], 'Java or Kotlin required'))
        for context in (patch.dict(os.environ, {'JOB_RADAR_DB_PATH': str(self.path), 'WORK24_AUTH_KEY': 'secret-key'}),
                        patch.object(config, '_ENV_LOADED', True),
                        patch('urllib.request.urlopen', side_effect=AssertionError('Unexpected real HTTP')),
                        patch('jobskillradar.discovery_pipeline.fetch_work24_postings', self.collector),
                        patch('jobskillradar.discovery_pipeline.fetch_posting_detail', self.fetcher)):
            context.start()
            self.addCleanup(context.stop)

    def app(self):
        return AppTest.from_file(str(ROOT / 'app.py'), default_timeout=20).run()

    def profile(self, owned=('Java',)):
        save_profile(db_path=self.path, target_roles=[BACKEND], owned_skills=list(owned))

    def test_missing_profile_explains_setup_without_guessing_or_network(self):
        app = self.app()
        self.assertFalse(app.exception)
        self.assertEqual(app.sidebar.radio(key='navigation').value, '새 공고 찾기')
        self.assertTrue(any('목표 직무' in i.value for i in app.info))
        self.assertFalse(any(b.key == 'discover_jobs' for b in app.button))
        self.collector.assert_not_called()

    def test_missing_key_disables_search_but_manual_workflow_remains_available(self):
        self.profile()
        with patch.dict(os.environ, {'WORK24_AUTH_KEY': ''}):
            app = self.app()
            self.assertTrue(app.button(key='discover_jobs').disabled)
            self.assertTrue(any('WORK24_AUTH_KEY' in i.value for i in app.info))
            self.assertTrue(any('자동 검색어: 백엔드, 서버 개발' == t.value for t in app.text))
            app.sidebar.radio(key='navigation').set_value('공고 직접 등록').run()
            self.assertTrue(app.text_area(key='manual_create_body'))
        self.collector.assert_not_called()

    def test_search_summary_new_bucket_open_raw_and_existing_comparison_view(self):
        self.profile()
        app = self.app()
        self.collector.assert_not_called()
        app.button(key='discover_jobs').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(self.collector.call_count, 2)
        self.assertEqual(self.fetcher.call_count, 1)
        self.assertEqual(next(m for m in app.metric if m.label == '새로 발견').value, '1')
        self.assertTrue(any('새로 발견 · 먼저 검토' in t.value for t in app.text))
        app.button(key='discovery_open_one').click().run()
        self.assertEqual(app.sidebar.radio(key='navigation').value, '공고 목록')
        self.assertIn('Java or Kotlin required', [t.value for t in app.text])
        app.checkbox(key='compare_work24_one').check().run()
        self.assertFalse(app.exception)
        self.assertIn('필수 요건: Java 또는 Kotlin (하나 이상) — 프로필 등록 기준 충족', [t.value for t in app.text])
        self.assertEqual(self.collector.call_count, 2)

    def test_rerun_filter_restart_and_profile_change_do_not_refetch(self):
        self.profile()
        app = self.app()
        app.button(key='discover_jobs').click().run()
        app.checkbox(key='discovery_only_new').check().run()
        app.selectbox(key='discovery_bucket').set_value('먼저 검토').run()
        app.run()
        restarted = self.app()
        self.assertFalse(restarted.exception)
        self.assertEqual(next(m for m in restarted.metric if m.label == '새로 발견').value, '1')
        self.profile(owned=())
        restarted.run()
        self.assertTrue(any('필수 요건 확인 필요' in t.value for t in restarted.text))
        self.assertTrue(any('검색 당시 프로필 버전 1 · 현재 비교 버전 2' in c.value for c in restarted.caption))
        self.assertEqual((self.collector.call_count, self.fetcher.call_count), (2, 1))
        self.assertEqual(len(list_discovery_runs(self.path)), 1)

    def test_partial_failure_is_visible_and_error_payload_is_never_rendered(self):
        self.profile()
        self.collector.side_effect = [[posting('one')], OSError('authKey=secret-key response body')]
        self.fetcher.side_effect = Work24Error('api_error')
        app = self.app()
        app.button(key='discover_jobs').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any('부분 완료' in w.value for w in app.warning))
        self.assertTrue(any('정보 부족' in t.value for t in app.text))
        text = str([t.value for t in app.text] + [i.value for i in app.info])
        self.assertNotIn('secret-key', text)
        self.assertNotIn('response body', text)
        self.assertTrue(any('상세 실패 1' in c.value and '검색어 실패 1' in c.value for c in app.caption))

    def test_failed_latest_run_can_open_previous_success_without_network(self):
        self.profile()
        app = self.app()
        app.button(key='discover_jobs').click().run()
        successful = app.selectbox(key='discovery_run').value
        self.collector.side_effect = Work24Error('api_error')
        app.button(key='discover_jobs').click().run()
        self.assertTrue(any('모든 검색어 요청' in e.value for e in app.error))
        calls = self.collector.call_count
        app.selectbox(key='discovery_run').set_value(successful).run()
        self.assertFalse(app.exception)
        self.assertTrue(any('먼저 검토' in t.value for t in app.text))
        self.assertEqual(self.collector.call_count, calls)

    def test_refresh_option_alone_never_fetches_and_second_search_reuses_by_default(self):
        self.profile()
        app = self.app()
        app.checkbox(key='discovery_refresh').check().run()
        self.collector.assert_not_called()
        app.checkbox(key='discovery_refresh').uncheck().run()
        app.button(key='discover_jobs').click().run()
        app.button(key='discover_jobs').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(self.fetcher.call_count, 1)
        self.assertEqual(next(m for m in app.metric if m.label == '새로 발견').value, '0')
        app.checkbox(key='discovery_refresh').check().run()
        app.button(key='discover_jobs').click().run()
        self.assertEqual(self.fetcher.call_count, 2)

    def test_unexpected_failure_shows_safe_message_and_no_fabricated_run(self):
        self.profile()
        self.collector.side_effect = RuntimeError('secret-key response body')
        app = self.app()
        app.button(key='discover_jobs').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any('저장하지 못했습니다' in e.value for e in app.error))
        self.assertNotIn('secret-key', str([e.value for e in app.error]))
        self.assertEqual(list_discovery_runs(self.path), [])

    def test_missing_key_after_restart_still_shows_saved_run_without_refetch(self):
        self.profile()
        app = self.app()
        app.button(key='discover_jobs').click().run()
        with patch.dict(os.environ, {'WORK24_AUTH_KEY': ''}):
            restarted = self.app()
            self.assertFalse(restarted.exception)
            self.assertTrue(restarted.button(key='discover_jobs').disabled)
            self.assertEqual(next(m for m in restarted.metric if m.label == '발견 공고').value, '1')
        self.assertEqual(self.collector.call_count, 2)

    def test_detail_url_is_available_when_list_url_is_missing(self):
        self.profile()
        self.collector.return_value = [posting('one', url='')]
        self.fetcher.side_effect = lambda **kw: clean_detail('one', detail_url='https://example.com/detail/one')
        app = self.app()
        app.button(key='discover_jobs').click().run()
        app.button(key='discovery_open_one').click().run()
        self.assertFalse(app.exception)
        links = app.get('link_button')
        self.assertTrue(any(link.proto.url == 'https://example.com/detail/one' for link in links))

    def test_paginated_results_and_budget_deferred_posting_without_extra_requests(self):
        self.profile()
        rows = [posting(f'p{i:02}') for i in range(21)]
        self.collector.side_effect = [rows[:11], rows[11:]]
        app = self.app()
        app.button(key='discover_jobs').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(self.fetcher.call_count, 20)
        self.assertEqual(len([b for b in app.button if b.label == '공고 열기']), 20)
        page = next(s for s in app.selectbox if s.label == '결과 페이지')
        page.set_value(2).run()
        self.assertEqual(len([b for b in app.button if b.label == '공고 열기']), 1)
        self.assertTrue(app.button(key='discovery_open_p20'))
        self.assertTrue(any('정보 부족' in t.value for t in app.text))
        self.assertEqual((self.collector.call_count, self.fetcher.call_count), (2, 20))
