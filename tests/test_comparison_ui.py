import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from jobskillradar import config, pipeline, storage
from jobskillradar.role_classifier import BACKEND


class ComparisonUiTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / 'journey.sqlite'
        for context in (patch.dict(os.environ, {'JOB_RADAR_DB_PATH': str(self.path), 'WORK24_AUTH_KEY': ''}),
                        patch.object(config, '_ENV_LOADED', True),
                        patch('urllib.request.urlopen', side_effect=AssertionError('Unexpected HTTP'))):
            context.start()
            self.addCleanup(context.stop)

    def app(self):
        return AppTest.from_file(str(ROOT / 'app.py'), default_timeout=15).run()

    def test_full_morning_manual_profile_comparison_restart_and_edit_journey(self):
        app = self.app()
        app.sidebar.radio(key='navigation').set_value('공고 직접 등록').run()
        app.text_input(key='manual_create_company').set_value('Example')
        app.text_input(key='manual_create_title').set_value('Backend Engineer')
        app.text_area(key='manual_create_body').set_value('Java or Kotlin required\nDocker preferred\nResponsibilities\nAWS\n기술스택: Python')
        next(b for b in app.button if b.label == '공고 등록').click().run()
        identity = app.selectbox(key='selected_posting').value
        app.sidebar.radio(key='navigation').set_value('내 프로필').run()
        app.text_area(key='profile_0_skills').set_value('Kotlin')
        app.multiselect(key='profile_0_roles').set_value([BACKEND])
        next(b for b in app.button if b.label == '프로필 저장').click().run()
        restarted = self.app()
        self.assertEqual(restarted.selectbox(key='selected_posting').value, identity)
        restarted.checkbox(key='compare_' + identity[0] + '_' + identity[1]).check().run()
        self.assertFalse(restarted.exception)
        texts = [t.value for t in restarted.text]
        self.assertIn('필수 요건: Java 또는 Kotlin (하나 이상) — 프로필 등록 기준 충족', texts)
        self.assertIn('Docker: 우대 기술이 프로필에 미등록 (필수 부족 아님)', texts)
        self.assertIn('AWS: 업무 관련 기술이 프로필에 미등록 (필수 부족 아님)', texts)
        self.assertFalse(any(t.startswith(('Java: 프로필에 등록되어', 'Kotlin: 프로필에 등록되어')) for t in texts))
        self.assertTrue(any('Python' in e.label and '분류하지 못한' in e.label for e in restarted.expander))
        next(t for t in restarted.text_area if t.label == '공고 본문 *').set_value('Java and SQL required')
        next(b for b in restarted.button if b.label == '수정 저장').click().run()
        self.assertFalse(restarted.exception)
        self.assertIn('필수 요건: SQL 그리고 Java (모두) — 현재 프로필 등록만으로 충족을 확인할 수 없음', [t.value for t in restarted.text])
        self.assertNotIn('Java', [m.value for m in restarted.markdown])
        self.assertNotIn('SQL', [m.value for m in restarted.markdown])
        self.assertTrue(restarted.json)

    def test_missing_profile_and_missing_work24_detail_are_not_success_verdicts(self):
        storage.save_postings_to_db(self.path, [{'source': 'work24', 'posting_id': 'w', 'title': 'Original'}])
        app = self.app()
        app.checkbox(key='compare_work24_w').check().run()
        self.assertFalse(app.exception)
        self.assertTrue(any('먼저' in i.value and '내 프로필' in i.value for i in app.info))
        pipeline.save_profile(db_path=self.path, owned_skills=['Java'], target_roles=[BACKEND])
        app.run()
        self.assertFalse(app.exception)
        self.assertTrue(any('상세 원문이 아직' in i.value for i in app.info))
        self.assertFalse(any('프로필 등록 기준 충족' in t.value for t in app.text))


if __name__ == '__main__':
    unittest.main()
