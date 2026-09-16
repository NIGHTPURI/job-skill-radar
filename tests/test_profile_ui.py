import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from jobskillradar import config, pipeline
from jobskillradar.role_classifier import BACKEND, DATA_ANALYST


class ProfileUiTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / 'profile-ui.sqlite'
        for context in (patch.dict(os.environ, {'JOB_RADAR_DB_PATH': str(self.path), 'WORK24_AUTH_KEY': ''}),
                        patch.object(config, '_ENV_LOADED', True),
                        patch('urllib.request.urlopen', side_effect=AssertionError('Unexpected HTTP'))):
            context.start()
            self.addCleanup(context.stop)

    def app(self):
        return AppTest.from_file(str(ROOT / 'app.py'), default_timeout=15).run()

    def test_save_restart_edit_and_market_defaults(self):
        app = self.app()
        app.sidebar.radio(key='navigation').set_value('내 프로필').run()
        app.text_area(key='profile_0_skills').set_value('springboot, postgres, k8s, Elixir')
        app.multiselect(key='profile_0_roles').set_value([BACKEND, DATA_ANALYST])
        app.multiselect(key='profile_0_preferred').set_value(['경기'])
        app.multiselect(key='profile_0_required').set_value(['서울'])
        next(b for b in app.button if b.label == '프로필 저장').click().run()
        self.assertFalse(app.exception)
        self.assertIn('Elixir', app.text_area(key='profile_1_skills').value)
        restarted = self.app()
        restarted.sidebar.radio(key='navigation').set_value('내 프로필').run()
        self.assertEqual(restarted.multiselect(key='profile_1_required').value, ['서울'])
        self.assertEqual(set(restarted.multiselect(key='profile_1_roles').value), {BACKEND, DATA_ANALYST})
        restarted.text_area(key='profile_1_skills').set_value('Python')
        next(b for b in restarted.button if b.label == '프로필 저장').click().run()
        self.assertFalse(restarted.exception)
        self.assertEqual(pipeline.load_profile(db_path=self.path)['revision'], 2)
        restarted.sidebar.radio(key='navigation').set_value('시장 분석').run()
        self.assertFalse(restarted.exception)
        self.assertEqual(restarted.text_input(key='market_skills_2').value, 'Python')
        restarted.text_input(key='market_skills_2').set_value('SQL').run()
        self.assertEqual(pipeline.load_profile(db_path=self.path)['owned_skills'], ['Python'])

    def test_missing_target_role_keeps_draft_without_creating_profile(self):
        app = self.app()
        app.sidebar.radio(key='navigation').set_value('내 프로필').run()
        app.text_area(key='profile_0_skills').set_value('SQL')
        next(b for b in app.button if b.label == '프로필 저장').click().run()
        self.assertTrue(app.error)
        self.assertFalse(app.exception)
        self.assertEqual(app.text_area(key='profile_0_skills').value, 'SQL')
        self.assertIsNone(pipeline.load_profile(db_path=self.path))

    def test_existing_v2_database_migrates_on_app_start_without_repeated_backup(self):
        with sqlite3.connect(self.path) as conn:
            conn.executescript((ROOT / 'tests/fixtures/v2_schema.sql').read_text())
            conn.execute("INSERT INTO job_postings(source,posting_id,title,created_at) VALUES ('work24','one','SQL','2000-01-01')")
        app = self.app()
        self.assertFalse(app.exception)
        self.assertEqual(len(list(self.path.parent.glob('*.pre-v4-from-v2-*.bak'))), 1)
        self.assertFalse(self.app().exception)
        self.assertEqual(len(list(self.path.parent.glob('*.bak'))), 1)
        with sqlite3.connect(self.path) as conn:
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 4)
            self.assertEqual(conn.execute('SELECT created_at FROM job_postings').fetchone()[0], '2000-01-01')


if __name__ == '__main__':
    unittest.main()
