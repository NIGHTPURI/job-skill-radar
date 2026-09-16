import importlib.util
import io
import sys
import tempfile
import unittest
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from jobskillradar import pipeline, storage

spec = importlib.util.spec_from_file_location("collect_work24_cli", ROOT / "scripts" / "collect_work24.py")
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)
FIXTURES = Path(__file__).parent / "fixtures" / "work24"


class CollectionCliTest(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.path = Path(self.stack.enter_context(tempfile.TemporaryDirectory())) / "cli.sqlite"
        self.stack.enter_context(patch.object(cli, "get_work24_auth_key", return_value="secret-key"))
        self.stack.enter_context(patch.object(cli, "get_db_path", return_value=self.path))
        self.stack.enter_context(patch.object(pipeline, "get_db_path", return_value=self.path))
        self.urlopen = self.stack.enter_context(patch("urllib.request.urlopen"))
        self.failure = False
        self.urlopen.side_effect = self.respond

    def respond(self, url, **kwargs):
        query = parse_qs(urlsplit(url).query)
        if query["callTp"] == ["L"]:
            return io.BytesIO((FIXTURES / "list.xml").read_bytes())
        identity = query["wantedAuthNo"][0]
        if self.failure and identity == "TEST-002":
            return io.BytesIO(b"<error><message>secret-key private-response</message></error>")
        xml = (FIXTURES / "detail.xml").read_text(encoding="utf-8").replace("TEST-001", identity)
        return io.BytesIO(xml.encode("utf-8"))

    def run_cli(self, *arguments):
        output = io.StringIO()
        code = 0
        with patch.object(sys, "argv", ["collect_work24.py", "--keyword", "SQL", *arguments]), \
                redirect_stdout(output), redirect_stderr(output):
            try:
                cli.main()
            except SystemExit as error:
                code = error.code
        self.assertNotIn("secret-key", output.getvalue())
        self.assertNotIn("private-response", output.getvalue())
        return code, output.getvalue()

    def test_default_is_list_only_with_legacy_output_and_exit_zero(self):
        code, output = self.run_cli()
        self.assertEqual(code, 0)
        self.assertIn("신규 저장: 2건", output)
        self.assertNotIn("Details saved", output)
        self.assertEqual(self.urlopen.call_count, 1)
        self.assertIsNone(storage.load_posting_detail_from_db(self.path, "work24", "TEST-001"))

    def test_enabled_details_success_reports_counts_and_exit_zero(self):
        code, output = self.run_cli("--with-details")
        self.assertEqual(code, 0)
        self.assertIn("Details saved: 2; failed: 0", output)
        self.assertEqual(self.urlopen.call_count, 3)
        self.assertIsNotNone(storage.load_posting_detail_from_db(self.path, "work24", "TEST-002"))

    def test_partial_failure_exits_two_after_preserving_successful_work(self):
        self.failure = True
        code, output = self.run_cli("--with-details")
        self.assertEqual(code, 2)
        self.assertIn("Details saved: 1; failed: 1", output)
        self.assertIn("work24/TEST-002 (api_error)", output)
        self.assertEqual(len(storage.load_postings_from_db(self.path)), 2)
        self.assertIsNotNone(storage.load_posting_detail_from_db(self.path, "work24", "TEST-001"))
        self.assertIsNone(storage.load_posting_detail_from_db(self.path, "work24", "TEST-002"))

    def test_list_failure_exits_one_without_response_or_key(self):
        self.urlopen.side_effect = TimeoutError("secret-key private-response")
        code, output = self.run_cli("--with-details")
        self.assertEqual(code, 1)
        self.assertIn("Collection failed: transport_error", output)
        self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()
