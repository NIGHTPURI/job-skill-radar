import io
import sys
import unittest
import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jobskillradar.work24_client import _parse_list_response, fetch_work24_postings

FIXTURE = Path(__file__).parent / "fixtures" / "work24" / "list.xml"


class Work24ParserTest(unittest.TestCase):
    def test_normal_response_all_fields_and_multiple_postings(self):
        postings = _parse_list_response(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(len(postings), 2)
        self.assertEqual(postings[0], {
            "source": "work24", "posting_id": "TEST-001", "company": "테스트 회사",
            "title": "Python 분석 담당", "description": "Python 분석 담당 정보서비스업 경력",
            "region": "서울 강남구", "career": "경력", "education": "대졸 ~ 박사",
            "salary_type": "연봉", "salary": "4000만원", "job_code": "134",
            "registered_at": "2026-09-01", "closing_at": "2026-09-30",
            "url": "https://example.com/jobs/1?a=1&b=2",
        })
        self.assertEqual(postings[1]["posting_id"], "TEST-002")

    def test_missing_empty_and_whitespace_tags_become_empty_strings(self):
        posting = _parse_list_response(FIXTURE.read_text(encoding="utf-8"))[1]
        self.assertEqual(posting["description"], "SQL 담당")
        self.assertEqual(posting["education"], "학력무관")
        for field in ("company", "career", "region", "salary", "salary_type", "job_code", "url", "registered_at", "closing_at"):
            with self.subTest(field=field):
                self.assertEqual(posting[field], "")

    def test_missing_id_and_title_are_not_rejected_by_parser(self):
        posting = _parse_list_response("<root><wanted/></root>")[0]
        self.assertEqual(posting["source"], "work24")
        self.assertTrue(all(value == "" for key, value in posting.items() if key != "source"))

    def test_education_composition_omits_empty_sides(self):
        for tags, expected in [("<minEdubg>대졸</minEdubg>", "대졸"),
                               ("<maxEdubg>박사</maxEdubg>", "박사"),
                               ("<minEdubg/><maxEdubg/>", "")]:
            with self.subTest(tags=tags):
                self.assertEqual(_parse_list_response(f"<root><wanted>{tags}</wanted></root>")[0]["education"], expected)

    def test_description_is_list_summary_not_full_job_description(self):
        # Synthetic extra tag is deliberately ignored, not an asserted Work24 detail field.
        xml = """<root><wanted><title>Developer</title><indTpNm>Software</indTpNm>
                 <career>Experienced</career><description>Required SQL; preferred Docker</description>
                 </wanted></root>"""
        posting = _parse_list_response(xml)[0]
        self.assertEqual(posting["description"], "Developer Software Experienced")
        self.assertNotIn("SQL", posting["description"])
        self.assertNotIn("Docker", posting["description"])

    def test_empty_result(self):
        self.assertEqual(_parse_list_response("<root/>"), [])

    def test_current_kd09_error_xml_is_indistinguishable_from_empty_result(self):
        """KD-09 / Phase 4B: synthetic error envelope silently becomes zero postings."""
        self.assertEqual(_parse_list_response("<error><message>invalid key</message></error>"), [])

    def test_malformed_xml_raises_parse_error(self):
        with self.assertRaises(ET.ParseError):
            _parse_list_response("<root>")

    def test_current_namespaced_wanted_nodes_are_not_matched(self):
        self.assertEqual(_parse_list_response('<root xmlns="urn:test"><wanted/></root>'), [])


class Work24RequestTest(unittest.TestCase):
    def setUp(self):
        # Every request test is intercepted, including validation-failure tests.
        patcher = patch("jobskillradar.work24_client.urllib.request.urlopen")
        self.urlopen = patcher.start()
        self.addCleanup(patcher.stop)
        self.urlopen.side_effect = lambda *args, **kwargs: io.BytesIO(b"<root/>")

    def query(self, index=0):
        return parse_qs(urlsplit(self.urlopen.call_args_list[index].args[0]).query)

    def test_missing_key_raises_before_request(self):
        with self.assertRaisesRegex(ValueError, "WORK24_AUTH_KEY"):
            fetch_work24_postings("", "SQL")
        self.urlopen.assert_not_called()

    def test_request_url_parameters_encoding_and_timeout(self):
        fetch_work24_postings("test-key", "데이터 & SQL", region="11000", occupation="134")
        self.assertEqual(self.query(), {
            "authKey": ["test-key"], "callTp": ["L"], "returnType": ["XML"],
            "startPage": ["1"], "display": ["100"], "sortOrderBy": ["DESC"],
            "keyword": ["데이터 & SQL"], "region": ["11000"], "occupation": ["134"],
        })
        url = urlsplit(self.urlopen.call_args.args[0])
        self.assertEqual((url.scheme, url.netloc, url.path),
                         ("https", "www.work24.go.kr", "/cm/openApi/call/wk/callOpenApiSvcInfo210L01.do"))
        self.assertEqual(self.urlopen.call_args.kwargs, {"timeout": 30})

    def test_empty_optional_parameters_are_omitted(self):
        fetch_work24_postings("test-key", "")
        for name in ("keyword", "region", "occupation"):
            self.assertNotIn(name, self.query())

    def test_page_minimum_and_display_bounds(self):
        for pages, display, expected in [(0, 0, "1"), (-2, -10, "1"), (1, 200, "100"), (1, 25, "25")]:
            with self.subTest(pages=pages, display=display):
                self.urlopen.reset_mock()
                fetch_work24_postings("test-key", "SQL", pages=pages, display=display)
                self.assertEqual(self.urlopen.call_count, 1)
                self.assertEqual(self.query()["startPage"], ["1"])
                self.assertEqual(self.query()["display"], [expected])

    def test_all_requested_pages_are_fetched_even_after_empty_page(self):
        fetch_work24_postings("test-key", "SQL", pages=3)
        self.assertEqual(self.urlopen.call_count, 3)
        self.assertEqual([self.query(i)["startPage"] for i in range(3)], [["1"], ["2"], ["3"]])

    def test_utf8_response_is_parsed_and_client_does_not_deduplicate(self):
        self.urlopen.side_effect = lambda *args, **kwargs: io.BytesIO(FIXTURE.read_bytes())
        postings = fetch_work24_postings("test-key", "SQL", pages=2)
        self.assertEqual([p["posting_id"] for p in postings], ["TEST-001", "TEST-002"] * 2)
        self.assertEqual(postings[0]["company"], "테스트 회사")

    def test_timeout_and_http_error_propagate_without_retry(self):
        for error in (TimeoutError("timed out"), urllib.error.HTTPError("https://example.com", 503, "unavailable", {}, None)):
            with self.subTest(error=type(error).__name__):
                self.urlopen.reset_mock()
                self.urlopen.side_effect = error
                with self.assertRaises(type(error)):
                    fetch_work24_postings("test-key", "SQL", pages=3)
                self.assertEqual(self.urlopen.call_count, 1)


if __name__ == "__main__":
    unittest.main()
