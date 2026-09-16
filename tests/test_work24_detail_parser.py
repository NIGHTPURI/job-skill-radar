import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jobskillradar.models import DETAIL_TEXT_FIELDS, DetailEvidence
from jobskillradar.work24_client import Work24Error, parse_posting_detail

FIXTURES = Path(__file__).parent / "fixtures" / "work24"
FULL_XML = (FIXTURES / "detail.xml").read_text(encoding="utf-8")
MINIMAL_XML = (FIXTURES / "detail_minimal.xml").read_text(encoding="utf-8")


class DetailParserTest(unittest.TestCase):
    def setUp(self):
        blocker = patch("urllib.request.urlopen", side_effect=AssertionError("Network forbidden"))
        blocker.start()
        self.addCleanup(blocker.stop)

    def assert_failure(self, xml, kind):
        with self.assertRaises(Work24Error) as raised:
            parse_posting_detail(xml)
        self.assertEqual(raised.exception.kind, kind)

    def test_full_document_contract_and_selected_fields(self):
        detail = parse_posting_detail(FULL_XML)
        self.assertEqual(set(detail), set(DetailEvidence.__annotations__))
        self.assertEqual((detail["source"], detail["posting_id"]), ("work24", "TEST-001"))
        expected = {
            "employment_type": "Permanent contract", "raw_career_condition": "경력무관",
            "education": "Bachelor degree or above", "foreign_language": "English reading",
            "major": "Computer science", "certificate": "정보처리기사 (우대)",
            "computer_skill": "Office software and spreadsheets",
            "preferred_conditions": "Relevant project experience",
            "other_preferred_conditions": "Spring Boot experience is a plus",
            "selection_method": "Document review\nInterview", "receipt_method": "Online application",
            "submit_documents": "Resume and portfolio", "work_region": "Seoul, Mapo-gu",
            "work_hours": "09:00-18:00, five days per week", "welfare": "Meals and training",
            "salary_condition": "Annual salary 40,000,000 KRW, negotiable", "closing_at": "2026-10-31",
        }
        for field, value in expected.items():
            with self.subTest(field=field):
                self.assertEqual(detail[field], value)
        self.assertNotIn("description", detail)
        self.assertNotIn("career", detail)
        self.assertNotIn("contactTelno", detail)

    def test_minimal_valid_detail_preserves_absence(self):
        detail = parse_posting_detail(MINIMAL_XML)
        self.assertEqual(detail["posting_id"], "TEST-001")
        self.assertTrue(all(detail[name] is None for name in DETAIL_TEXT_FIELDS))
        self.assertEqual(detail["keywords"], [])
        self.assertNotIn("fetched_at", detail)

    def test_empty_and_whitespace_optional_tags_are_none(self):
        detail = parse_posting_detail(MINIMAL_XML.replace(
            "<wantedInfo/>", "<wantedInfo><jobCont/><eduNm> \n </eduNm><certificate/><enterTpNm/></wantedInfo>"))
        for field in ("job_content", "education", "certificate", "raw_career_condition"):
            self.assertIsNone(detail[field])

    def test_multiline_escaping_and_cdata_preserve_meaning(self):
        detail = parse_posting_detail(FULL_XML)
        self.assertEqual(detail["job_content"],
                         "Build APIs with Java & SQL.\n  Maintain services <daily>.\n\nReview changes with the team.")
        self.assertEqual(detail["other_information"], "Bring examples; <no originals required>.")
        self.assertEqual(detail["detail_url"], "https://example.com/details/1?a=1&b=2")

    def test_keywords_keep_source_order_and_duplicates(self):
        self.assertEqual(parse_posting_detail(FULL_XML)["keywords"], ["Java", "API development", "Java"])

    def test_default_namespace_keeps_nested_contract(self):
        xml = MINIMAL_XML.replace("<wantedDtl>", '<wantedDtl xmlns="urn:test">')
        self.assertEqual(parse_posting_detail(xml), parse_posting_detail(MINIMAL_XML))

    def test_malformed_xml_is_failure(self):
        for xml in ("", "<wantedDtl>", "<wantedDtl>&unknown;</wantedDtl>"):
            with self.subTest(xml=xml):
                self.assert_failure(xml, "malformed_xml")

    def test_missing_detail_node_is_failure(self):
        for xml in ("<wantedDtl/>", "<wantedDtl><wantedAuthNo>A</wantedAuthNo></wantedDtl>", "<wantedRoot/>"):
            with self.subTest(xml=xml):
                self.assert_failure(xml, "missing_detail")

    def test_missing_or_blank_identity_is_failure(self):
        for tag in ("", "<wantedAuthNo/>", "<wantedAuthNo> </wantedAuthNo>"):
            self.assert_failure(f"<wantedDtl>{tag}<wantedInfo/></wantedDtl>", "missing_identity")

    def test_api_error_shapes_never_become_empty_success(self):
        for xml in ("<error><message>invalid key</message></error>",
                    "<message><errorCd>AUTH</errorCd></message>",
                    '<error xmlns="urn:test"/>',
                    MINIMAL_XML.replace("<wantedInfo/>", "<wantedInfo/><error/>")):
            self.assert_failure(xml, "api_error")

    def test_unexpected_structure_is_failure(self):
        for xml in ("<html><body>Unavailable</body></html>", "<response/>",
                    f"<wrapper>{MINIMAL_XML.split('?>')[1]}</wrapper>",
                    MINIMAL_XML.replace("<wantedInfo/>", "<wantedInfo/><wantedInfo/>"),
                    MINIMAL_XML.replace("<wantedInfo/>", "<wantedInfo>Unavailable</wantedInfo>"),
                    MINIMAL_XML.replace("<wantedDtl>", "<wantedDtl>Unavailable"),
                    MINIMAL_XML.replace("<wantedInfo/>", "<wantedInfo><jobCont/>Unavailable</wantedInfo>"),
                    MINIMAL_XML.replace("<wantedInfo/>", "<wantedInfo><unknown>data</unknown></wantedInfo>")):
            with self.subTest(xml=xml):
                self.assert_failure(xml, "unexpected_structure")

    def test_nested_or_duplicate_scalar_is_rejected_without_truncation(self):
        for tags in ("<jobCont><paragraph>text</paragraph></jobCont>", "<jobCont>A</jobCont><jobCont>B</jobCont>"):
            self.assert_failure(MINIMAL_XML.replace("<wantedInfo/>", f"<wantedInfo>{tags}</wantedInfo>"),
                                "unexpected_structure")

    def test_wrong_parent_fields_are_not_used(self):
        xml = MINIMAL_XML.replace("<wantedInfo/>", "<corpInfo><jobCont>SQL</jobCont></corpInfo><wantedInfo/>")
        self.assertIsNone(parse_posting_detail(xml)["job_content"])

    def test_unexpected_keyword_structure_is_rejected(self):
        for value in ("Java, SQL", "<unknown>Java</unknown>", "<srchKeywordNm><value>Java</value></srchKeywordNm>",
                      "<srchKeywordNm>Java</srchKeywordNm>SQL"):
            xml = MINIMAL_XML.replace("<wantedInfo/>", f"<wantedInfo><keywordList>{value}</keywordList></wantedInfo>")
            self.assert_failure(xml, "unexpected_structure")


if __name__ == "__main__":
    unittest.main()
