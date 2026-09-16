import os
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jobskillradar import config


class ConfigTest(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.root = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        stack.enter_context(patch.dict(os.environ, {}, clear=True))
        stack.enter_context(patch.object(config, "PROJECT_ROOT", self.root))
        stack.enter_context(patch.object(config, "DEFAULT_DB_PATH", self.root / "data" / "default.sqlite"))
        stack.enter_context(patch.object(config, "_ENV_LOADED", False))

    def test_env_parsing_quotes_comments_and_existing_environment_priority(self):
        (self.root / ".env").write_text(
            '# comment\ninvalid\nWORK24_AUTH_KEY="file-key"\nJOB_RADAR_DB_PATH= custom/test.sqlite \n'
            "EXTRA='a=b'\n=ignored\n", encoding="utf-8")
        os.environ["WORK24_AUTH_KEY"] = " environment-key "
        self.assertEqual(config.get_work24_auth_key(), "environment-key")
        self.assertEqual(config.get_db_path(), self.root / "custom" / "test.sqlite")
        self.assertEqual(os.environ["EXTRA"], "a=b")

    def test_default_path_and_empty_key_without_env_file(self):
        self.assertEqual(config.get_work24_auth_key(), "")
        self.assertEqual(config.get_db_path(), self.root / "data" / "default.sqlite")

    def test_absolute_path_is_not_rebased(self):
        path = self.root / "absolute.sqlite"
        os.environ["JOB_RADAR_DB_PATH"] = str(path)
        self.assertEqual(config.get_db_path(), path)

    def test_current_env_file_is_only_loaded_once(self):
        path = self.root / ".env"
        path.write_text("WORK24_AUTH_KEY=first", encoding="utf-8")
        self.assertEqual(config.get_work24_auth_key(), "first")
        path.write_text("WORK24_AUTH_KEY=second", encoding="utf-8")
        self.assertEqual(config.get_work24_auth_key(), "first")

    def test_current_missing_file_also_marks_environment_loaded(self):
        self.assertEqual(config.get_work24_auth_key(), "")
        (self.root / ".env").write_text("WORK24_AUTH_KEY=late-key", encoding="utf-8")
        self.assertEqual(config.get_work24_auth_key(), "")


if __name__ == "__main__":
    unittest.main()
