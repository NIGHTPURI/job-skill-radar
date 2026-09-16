import io
import sys
import traceback
import unittest
import urllib.error
from datetime import datetime, timedelta
from http.client import IncompleteRead
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jobskillradar.work24_client import Work24Error, fetch_posting_detail

FIXTURE = Path(__file__).parent / "fixtures" / "work24" / "detail.xml"


class DetailRequestTest(unittest.TestCase):
    def setUp(self):
        patcher = patch("jobskillradar.work24_client.urllib.request.urlopen")
        self.urlopen = patcher.start()
        self.addCleanup(patcher.stop)
        self.urlopen.side_effect = lambda *args, **kwargs: io.BytesIO(FIXTURE.read_bytes())

    def test_endpoint_parameters_encoding_and_timeout(self):
        fetch_posting_detail("test & key", "TEST-001")
        url = urlsplit(self.urlopen.call_args.args[0])
        self.assertEqual((url.scheme, url.netloc, url.path),
                         ("https", "www.work24.go.kr", "/cm/openApi/call/wk/callOpenApiSvcInfo210D01.do"))
        self.assertEqual(parse_qs(url.query), {
            "authKey": ["test & key"], "wantedAuthNo": ["TEST-001"],
            "callTp": ["D"], "returnType": ["XML"], "infoSvc": ["VALIDATION"],
        })
        self.assertEqual(self.urlopen.call_args.kwargs, {"timeout": 30})
        self.assertEqual(self.urlopen.call_count, 1)

    def test_successful_fetch_adds_utc_timestamp_and_decodes_utf8(self):
        before = datetime.now().astimezone()
        detail = fetch_posting_detail("fake", "TEST-001")
        timestamp = datetime.fromisoformat(detail["fetched_at"])
        self.assertEqual(timestamp.utcoffset(), timedelta(0))
        self.assertLessEqual(before, timestamp)
        self.assertLessEqual(timestamp, datetime.now().astimezone())
        self.assertEqual(detail["raw_career_condition"], "경력무관")

    def test_invalid_inputs_fail_before_network(self):
        for key, posting_id in (("", "A"), (" ", "A"), ("fake", ""), ("fake", " \t")):
            with self.assertRaises(ValueError):
                fetch_posting_detail(key, posting_id)
        self.urlopen.assert_not_called()

    def test_response_identity_must_match_request(self):
        with self.assertRaises(Work24Error) as raised:
            fetch_posting_detail("fake", "DIFFERENT")
        self.assertEqual(raised.exception.kind, "identity_mismatch")

    def test_transport_failures_are_safe_and_not_retried(self):
        auth_key = "secret-key"
        for error in (TimeoutError("secret-key"), urllib.error.URLError("secret-key"),
                      urllib.error.HTTPError("https://example.com/?authKey=secret-key", 503, "offline", {}, None),
                      IncompleteRead(b"secret-key")):
            with self.subTest(error=type(error).__name__):
                self.urlopen.reset_mock()
                self.urlopen.side_effect = error
                try:
                    fetch_posting_detail(auth_key, "TEST-001")
                except Work24Error as failure:
                    self.assertEqual(failure.kind, "transport_error")
                    self.assertNotIn("secret-key", "".join(traceback.format_exception(failure)))
                else:
                    self.fail("Transport failure was accepted")
                self.assertEqual(self.urlopen.call_count, 1)

    def test_invalid_utf8_is_failure(self):
        self.urlopen.side_effect = lambda *a, **kw: io.BytesIO(b"\xff\xfe")
        with self.assertRaises(Work24Error) as raised:
            fetch_posting_detail("fake", "TEST-001")
        self.assertEqual(raised.exception.kind, "invalid_encoding")

    def test_response_is_closed_when_parsing_fails(self):
        response = io.BytesIO(b"<wantedDtl>")
        self.urlopen.side_effect = None
        self.urlopen.return_value = response
        with self.assertRaises(Work24Error) as raised:
            fetch_posting_detail("fake", "TEST-001")
        self.assertEqual(raised.exception.kind, "malformed_xml")
        self.assertTrue(response.closed)

    def test_api_failure_is_propagated_without_body_or_key(self):
        self.urlopen.side_effect = lambda *a, **kw: io.BytesIO(b"<error><message>secret-key</message></error>")
        with self.assertRaises(Work24Error) as raised:
            fetch_posting_detail("secret-key", "TEST-001")
        self.assertEqual(raised.exception.kind, "api_error")
        self.assertNotIn("secret-key", str(raised.exception))

    def test_error_category_cannot_contain_arbitrary_response_text(self):
        error = Work24Error("https://example.com?authKey=secret-key")
        self.assertEqual(error.kind, "request_error")
        self.assertNotIn("secret-key", str(error))


if __name__ == "__main__":
    unittest.main()
