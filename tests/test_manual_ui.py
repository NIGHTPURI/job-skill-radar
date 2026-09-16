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


class ManualUiTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / 'ui.sqlite'
        for context in (patch.dict(os.environ, {'JOB_RADAR_DB_PATH': str(self.path), 'WORK24_AUTH_KEY': ''}),
                        patch.object(config, '_ENV_LOADED', True),
                        patch('urllib.request.urlopen', side_effect=AssertionError('Unexpected HTTP'))):
            context.start()
            self.addCleanup(context.stop)

    def app(self):
        return AppTest.from_file(str(ROOT / 'app.py'), default_timeout=15).run()

    def test_create_restart_edit_and_alternative_display(self):
        app = self.app()
        app.sidebar.radio(key='navigation').set_value('공고 직접 등록').run()
        app.text_input(key='manual_create_company').set_value('Example')
        app.text_input(key='manual_create_title').set_value('Backend Engineer')
        app.text_area(key='manual_create_body').set_value('Java or Kotlin required')
        next(b for b in app.button if b.label == '공고 등록').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.sidebar.radio(key='navigation').value, '공고 목록')
        self.assertIn('필수 요건: Java 또는 Kotlin — 하나 이상', [m.value for m in app.markdown])
        identity = app.selectbox(key='selected_posting').value
        restarted = self.app()
        self.assertFalse(restarted.exception)
        self.assertEqual(restarted.selectbox(key='selected_posting').value, identity)
        self.assertIn('Java or Kotlin required', [t.value for t in restarted.text])
        next(t for t in restarted.text_area if t.label == '공고 본문 *').set_value('Python required')
        next(b for b in restarted.button if b.label == '수정 저장').click().run()
        self.assertFalse(restarted.exception)
        self.assertEqual(restarted.selectbox(key='selected_posting').value, identity)
        self.assertIn('Python required', [t.value for t in restarted.text])
        review = pipeline.load_posting_review(*identity, db_path=self.path)
        self.assertEqual([s['skill'] for s in review['requirements']['skills']], ['Python'])

    def test_validation_keeps_input_and_work24_has_no_edit_form(self):
        app = self.app()
        app.sidebar.radio(key='navigation').set_value('공고 직접 등록').run()
        app.text_area(key='manual_create_body').set_value('Keep this draft')
        next(b for b in app.button if b.label == '공고 등록').click().run()
        self.assertTrue(app.error)
        self.assertEqual(app.text_area(key='manual_create_body').value, 'Keep this draft')
        self.assertEqual(pipeline.list_saved_postings(db_path=self.path), [])
        storage.save_postings_to_db(self.path, [{'source': 'work24', 'posting_id': 'w', 'title': 'Original'}])
        restarted = self.app()
        self.assertFalse(restarted.exception)
        self.assertNotIn('수정 저장', [b.label for b in restarted.button])
        self.assertIn('상세 원문이 아직 저장되지 않았습니다.', [i.value for i in restarted.info])

    def test_market_view_labels_sample_and_excludes_manual_selection(self):
        pipeline.create_manual_posting(db_path=self.path, company='Example', title='Java', body='Java required')
        app = self.app()
        app.sidebar.radio(key='navigation').set_value('시장 분석').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, '샘플')
        self.assertEqual(app.metric[1].value, '12')


if __name__ == '__main__':
    unittest.main()
