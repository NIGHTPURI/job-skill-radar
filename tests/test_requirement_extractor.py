import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jobskillradar.models import DETAIL_TEXT_FIELDS
from jobskillradar.requirement_extractor import REQUIREMENT_EXTRACTOR_VERSION, extract_requirements
from jobskillradar.skill_taxonomy import SKILL_DEFINITIONS
from jobskillradar.work24_client import parse_posting_detail

FIXTURE = Path(__file__).parent / "fixtures" / "requirements" / "evaluation.json"


def source_detail(**fields):
    return {**dict.fromkeys(DETAIL_TEXT_FIELDS), "source": "work24", "posting_id": "synthetic",
            "keywords": [], "fetched_at": "2026-09-17T00:00:00+00:00", **fields}


def classifications(result):
    return {item["skill"]: item["requirement_type"] for item in result["skills"]}


class RequirementExtractorTest(unittest.TestCase):
    def setUp(self):
        for target in ("urllib.request.urlopen", "sqlite3.connect"):
            blocker = patch(target, side_effect=AssertionError("Pure extraction must not perform I/O"))
            blocker.start()
            self.addCleanup(blocker.stop)

    def assert_provenance(self, detail, result):
        items = [e for skill in result["skills"] for e in skill["evidence"]]
        items += result["unclassified_evidence"]
        items += [group["evidence"] for group in result["groups"]]
        for evidence in items:
            field = detail[evidence["source_field"]]
            if evidence["source_index"] is not None:
                field = field[evidence["source_index"]]
            self.assertEqual(field[evidence["evidence_start"]:evidence["evidence_end"]], evidence["evidence_text"])
            self.assertTrue(evidence["evidence_text"].strip())
            self.assertTrue(evidence["rule"])
            if evidence["section_heading"] is not None:
                start = evidence["section_start"]
                self.assertEqual(field[start:start + len(evidence["section_heading"])], evidence["section_heading"])

    def test_manually_reviewed_evaluation_cases(self):
        cases = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(len({case["id"] for case in cases}), len(cases))
        for case in cases:
            with self.subTest(case=case["id"]):
                self.assertTrue(case["review_note"])
                detail = source_detail(**case["detail"])
                result = extract_requirements(detail)
                self.assertEqual(classifications(result), case["expected"])
                self.assertEqual(result["quality_status"], case["quality"])
                self.assert_provenance(detail, result)

    def test_explicit_required_cues_are_local(self):
        for text in ("Java 경험 필수", "Java 경험은 필수입니다", "Java 사용 경험이 필요합니다",
                     "반드시 Java 경험 보유", "Must have Java experience", "Java experience required"):
            with self.subTest(text=text):
                result = extract_requirements(source_detail(job_content=text))
                self.assertEqual(classifications(result), {"Java": "required"})
                self.assertEqual(result["skills"][0]["evidence"][0]["rule"], "explicit_required")

    def test_explicit_preferred_cues_override_required_section(self):
        for text in ("Kafka 경험자 우대", "Kafka 경험 우대", "Kafka 사용 경험은 plus",
                     "Kafka experience preferred", "Kafka is nice to have"):
            with self.subTest(text=text):
                result = extract_requirements(source_detail(job_content="자격요건\n" + text))
                self.assertEqual(classifications(result), {"Kafka": "preferred"})
                self.assertEqual(result["skills"][0]["evidence"][0]["rule"], "explicit_preferred")

    def test_duties_without_heading_do_not_assert_prior_experience(self):
        for text, expected in (("Java/Spring Boot 기반 API 개발", {"Java": "responsibility", "Spring Boot": "responsibility"}),
                               ("Kafka 데이터 파이프라인 운영", {"Kafka": "responsibility"}),
                               ("AWS 환경 서비스 배포", {"AWS": "responsibility"}),
                               ("Deploy services on AWS", {"AWS": "responsibility"}),
                               ("Java 개발 경험", {"Java": "unspecified"})):
            with self.subTest(text=text):
                self.assertEqual(classifications(extract_requirements(source_detail(job_content=text))), expected)

    def test_obvious_negation_wins_over_sections_and_preferred_fields(self):
        cases = {"AWS": "AWS 경험은 필수가 아닙니다", "Kubernetes": "Kubernetes 경험 없어도 지원 가능",
                 "Python": "Python 경험은 요구하지 않습니다", "Docker": "Docker experience is not required",
                 "SQL": "No SQL experience required", "Java": "We do not require Java experience"}
        for skill, text in cases.items():
            for field in ("job_content", "preferred_conditions"):
                with self.subTest(text=text, field=field):
                    result = extract_requirements(source_detail(**{field: "Requirements\n" + text}))
                    self.assertEqual(classifications(result), {skill: "unspecified"})
                    self.assertEqual(result["skills"][0]["evidence"][0]["rule"], "negated")
        for text in ("Java 필수 아님", "Java가 필수는 아닌 업무", "Java is not a requirement", "Java 경험 우대하지 않습니다"):
            self.assertEqual(classifications(extract_requirements(source_detail(job_content="Requirements\n" + text))),
                             {"Java": "unspecified"})

    def test_unsupported_formatted_heading_stops_required_scope_without_losing_mentions(self):
        for heading in ("<b>Preferred</b>", "[Tools Python]", "## Other Python", "| Preferred | Python |"):
            detail = source_detail(job_content="Requirements\nJava\n" + heading + "\nDocker")
            result = extract_requirements(detail)
            self.assertEqual(classifications(result)["Java"], "required")
            self.assertEqual(classifications(result)["Docker"], "unspecified")
            if "Python" in heading:
                self.assertEqual(classifications(result)["Python"], "unspecified")
            self.assert_provenance(detail, result)

    def test_cue_conflicts_and_questions_do_not_use_precedence_within_one_clause(self):
        for text in ("Java 필수 또는 우대", "Java required or preferred", "Java 필수 여부 미정",
                     "Is Java required?", '"Java required" is an example', "If Java is required"):
            with self.subTest(text=text):
                self.assertEqual(classifications(extract_requirements(source_detail(job_content=text))), {"Java": "unspecified"})

    def test_generic_cue_words_do_not_prove_technology_possession(self):
        for text in ("Java 버전 업그레이드가 필요합니다", "반드시 Java 서버를 점검합니다",
                     "Java 회의 참석 필수", "Java developers are required to attend a meeting"):
            with self.subTest(text=text):
                self.assertEqual(classifications(extract_requirements(source_detail(job_content=text))), {"Java": "unspecified"})
        self.assertEqual(classifications(extract_requirements(source_detail(job_content="Java plus Python"))),
                         {"Java": "unspecified", "Python": "unspecified"})
        self.assertEqual(classifications(extract_requirements(source_detail(job_content="Requirements\nJava optional"))),
                         {"Java": "unspecified"})

    def test_same_line_independent_clauses_keep_separate_scope(self):
        result = extract_requirements(source_detail(job_content="Java required, Python; Docker preferred. SQL"))
        self.assertEqual(classifications(result), {"Java": "required", "Python": "unspecified", "Docker": "preferred", "SQL": "unspecified"})

    def test_alternatives_and_mixed_conjunction_scope_are_not_individual_requirements(self):
        for text in ("Java 또는 Python 중 하나", "Java or Python", "Java required and Python mentioned",
                     "Java 필수 및 Python 소개"):
            with self.subTest(text=text):
                result = extract_requirements(source_detail(job_content="Requirements\n" + text))
                self.assertEqual(classifications(result), {"Java": "unspecified", "Python": "unspecified"})

    def test_heading_wrappers_blank_lines_and_section_changes(self):
        text = "  1. 자격요건： Java\r\n\r\n SQL\r\n**우대사항**\r\nDocker\r\n[업무내용]\r\nKafka\r\n## Benefits\r\nPython"
        detail = source_detail(job_content=text)
        result = extract_requirements(detail)
        self.assertEqual(classifications(result), {"Java": "required", "SQL": "required", "Docker": "preferred",
                                                   "Kafka": "responsibility", "Python": "unspecified"})
        self.assert_provenance(detail, result)

    def test_ordinary_prose_is_not_a_heading(self):
        for text in ("Responsibilities include Java", "Requirements are discussed with Java teams",
                     "자격요건 안내 Java", "주요업무 설명 Java"):
            with self.subTest(text=text):
                result = extract_requirements(source_detail(job_content=text))
                self.assertEqual(classifications(result), {"Java": "unspecified"})
                self.assertIsNone(result["skills"][0]["evidence"][0]["section_heading"])

    def test_preferred_field_default_and_explicit_contradictions(self):
        for field in ("preferred_conditions", "other_preferred_conditions"):
            result = extract_requirements(source_detail(**{field: "Java\nSQL 필수\nDocker not required\nResponsibilities\nKafka"}))
            self.assertEqual(classifications(result), {"Java": "preferred", "SQL": "required", "Docker": "unspecified", "Kafka": "responsibility"})

    def test_sections_do_not_leak_between_fields(self):
        result = extract_requirements(source_detail(job_content="Requirements\nJava", certificate="AWS",
                                                    computer_skill="SQL", other_information="Python",
                                                    preferred_conditions="Docker"))
        self.assertEqual(classifications(result), {"Java": "required", "AWS": "unspecified", "SQL": "unspecified",
                                                   "Python": "unspecified", "Docker": "preferred"})

    def test_keywords_are_always_metadata_and_keep_duplicates(self):
        detail = source_detail(keywords=["Java required", "Java required", "postgres", "", "not a technology"])
        result = extract_requirements(detail)
        self.assertEqual(classifications(result), {"Java": "unspecified", "PostgreSQL": "unspecified"})
        java = next(item for item in result["skills"] if item["skill"] == "Java")
        self.assertEqual([e["source_index"] for e in java["evidence"]], [0, 1])
        self.assertEqual(result["unclassified_evidence"][0]["source_index"], 4)
        self.assert_provenance(detail, result)

    def test_aggregation_retains_all_occurrences_and_their_own_classes(self):
        detail = source_detail(job_content="Java\nJava 개발\nJava 경험 우대\nJava 필수\nJava 필수\nJava not required")
        result = extract_requirements(detail)
        self.assertEqual(classifications(result), {"Java": "required"})
        evidence = result["skills"][0]["evidence"]
        self.assertEqual([e["requirement_type"] for e in evidence],
                         ["unspecified", "responsibility", "preferred", "required", "required", "unspecified"])
        self.assertEqual(len({e["evidence_start"] for e in evidence}), 6)
        self.assert_provenance(detail, result)

    def test_aliases_and_longest_overlap_without_parent_or_ecosystem_inference(self):
        before = copy.deepcopy(SKILL_DEFINITIONS)
        result = extract_requirements(source_detail(job_content="Required skills: springboot, postgres, k8s, JPA, AWS"))
        self.assertEqual(classifications(result), dict.fromkeys(["Spring Boot", "PostgreSQL", "Kubernetes", "JPA", "AWS"], "required"))
        self.assertEqual(SKILL_DEFINITIONS, before)
        self.assertFalse({"Spring", "Spring MVC", "Spring Security", "Hibernate", "Docker"} & classifications(result).keys())

    def test_unicode_offsets_and_version_are_deterministic_without_mutation(self):
        detail = source_detail(job_content="【자격요건】\r\n  • ß Java 경험 필수\r\n  SQL 역량 필수", keywords=["Java"])
        original = copy.deepcopy(detail)
        first = extract_requirements(detail)
        second = extract_requirements(detail)
        self.assertEqual(first, second)
        self.assertEqual(first["extractor_version"], REQUIREMENT_EXTRACTOR_VERSION)
        self.assertEqual(REQUIREMENT_EXTRACTOR_VERSION, 2)
        self.assertEqual(first["detail_fetched_at"], detail["fetched_at"])
        self.assertEqual(detail, original)
        self.assert_provenance(detail, first)
        first["skills"][0]["evidence"].clear()
        self.assertEqual(extract_requirements(detail), second)

    def test_quality_distinguishes_missing_empty_unclassified_and_extracted(self):
        cases = [(None, "detail_not_fetched"), (source_detail(), "detail_fetched_but_no_requirement_evidence"),
                 (source_detail(job_content="Welcome to our team"), "detail_fetched_but_no_requirement_evidence"),
                 (source_detail(job_content="Java"), "requirement_evidence_present_but_unclassified"),
                 (source_detail(job_content="Go experience required"), "requirement_evidence_present_but_unclassified"),
                 (source_detail(job_content="Java 필수"), "requirements_extracted")]
        for detail, expected in cases:
            with self.subTest(expected=expected, detail=detail):
                self.assertEqual(extract_requirements(detail)["quality_status"], expected)

    def test_non_skill_conditions_preserve_raw_and_only_normalize_exact_career_categories(self):
        detail = source_detail(raw_career_condition=" 경력무관 ", education="학사 또는 동등 경험",
                               employment_type="계약직 협의", work_region="서울 또는 재택")
        result = extract_requirements(detail)
        conditions = {item["source_field"]: item for item in result["conditions"]}
        self.assertEqual(conditions["raw_career_condition"], {"source_field": "raw_career_condition", "raw_text": " 경력무관 ",
                                                            "status": "normalized", "normalized_value": "무관"})
        for field in ("education", "employment_type", "work_region"):
            self.assertEqual(conditions[field]["raw_text"], detail[field])
            self.assertEqual(conditions[field]["status"], "not_interpreted")
            self.assertIsNone(conditions[field]["normalized_value"])
        self.assertEqual(result["quality_status"], "requirement_evidence_present_but_unclassified")
        for raw in ("경력 3년 이상", "신입 가능 여부 협의", "무관하지 않음", "미상", None, ""):
            condition = extract_requirements(source_detail(raw_career_condition=raw))["conditions"][0]
            self.assertIsNone(condition["normalized_value"])
            self.assertEqual(condition["status"], "not_interpreted" if raw else "missing")

    def test_invalid_source_values_raise_instead_of_empty_success(self):
        for changes in ({"job_content": 1}, {"keywords": None}, {"keywords": [1]}, {"education": []}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                extract_requirements(source_detail(**changes))

    def test_unrelated_fields_do_not_create_technical_requirements(self):
        result = extract_requirements(source_detail(detail_url="https://example.com/Java", salary_condition="SQL required",
                                                    receipt_method="Python preferred", welfare="Docker books"))
        self.assertEqual(result["skills"], [])
        self.assertEqual(result["quality_status"], "detail_fetched_but_no_requirement_evidence")

    def test_work24_fixture_uses_source_fields_without_changing_parser_evidence(self):
        path = Path(__file__).parent / "fixtures" / "work24" / "detail.xml"
        detail = parse_posting_detail(path.read_text(encoding="utf-8"))
        original = copy.deepcopy(detail)
        result = extract_requirements(detail)
        self.assertEqual(classifications(result), {"Java": "responsibility", "SQL": "responsibility", "Spring Boot": "preferred"})
        spring = next(item for item in result["skills"] if item["skill"] == "Spring Boot")
        self.assertEqual(spring["evidence"][0]["source_field"], "other_preferred_conditions")
        self.assertEqual(spring["evidence"][0]["evidence_text"], "Spring Boot experience is a plus")
        self.assertIsNone(result["detail_fetched_at"])
        self.assertEqual(detail, original)
        self.assert_provenance(detail, result)

    def test_bounded_shared_cues_form_all_of_groups(self):
        for text, kind in (("Java and SQL required", "required"), ("Java와 SQL 경험 필수", "required"),
                           ("Java 및 SQL 사용 경험이 필요합니다", "required"),
                           ("Must have Java and SQL experience", "required"),
                           ("Java, SQL 경험자 우대", "preferred")):
            with self.subTest(text=text):
                detail = source_detail(job_content=text)
                result = extract_requirements(detail)
                self.assertEqual(classifications(result), {"Java": kind, "SQL": kind})
                self.assertEqual(len(result["groups"]), 1)
                group = result["groups"][0]
                self.assertEqual((group["relation"], group["requirement_type"], group["skills"]),
                                 ("all_of", kind, ["SQL", "Java"]))
                self.assertEqual(group["evidence"]["evidence_text"], text)
                self.assert_provenance(detail, result)

    def test_any_of_class_is_never_an_independent_member_requirement(self):
        for text, field, kind in (("Java 또는 Kotlin 중 하나 경험 필수", "job_content", "required"),
                                  ("Java or Kotlin required", "job_content", "required"),
                                  ("Java/Kotlin 중 하나 이상", "job_content", "unspecified"),
                                  ("Java 또는 Kotlin", "preferred_conditions", "preferred")):
            with self.subTest(text=text):
                detail = source_detail(**{field: text})
                result = extract_requirements(detail)
                self.assertEqual(classifications(result), {"Java": "unspecified", "Kotlin": "unspecified"})
                group = result["groups"][0]
                self.assertEqual((group["relation"], group["requirement_type"]), ("any_of", kind))
                self.assertEqual(group["evidence"]["requirement_type"], kind)
                for skill in result["skills"]:
                    self.assertEqual(skill["evidence"][0]["requirement_type"], "unspecified")
                    self.assertEqual(skill["evidence"][0]["relation"], "any_of")
                self.assert_provenance(detail, result)

    def test_unsupported_nested_or_unknown_choices_never_shrink_to_known_members(self):
        for text in ("Java or Elixir required", "Java and SQL or Python required",
                     "(Java and SQL) or Python required", "Java/SQL required",
                     "Java required and Python mentioned", "Java, Elixir 또는 Kotlin 필수"):
            with self.subTest(text=text):
                result = extract_requirements(source_detail(job_content="Requirements\n" + text))
                self.assertTrue(result["skills"])
                self.assertTrue(all(s["requirement_type"] == "unspecified" for s in result["skills"]))
                self.assertEqual(result["groups"], [])

    def test_negated_shared_list_and_negative_heading_end_positive_scope(self):
        for text in ("Java, SQL not required", "Java and SQL experience not necessary", "Java, SQL 필수가 아님",
                     "Java, SQL 필수가 아닙니다", "Java, SQL 경험은 요구하지 않습니다",
                     "Java, SQL 경험 없어도 지원 가능", "Java, SQL 경험 없어도 지원 가능합니다",
                     "Java, SQL experience is not required", "Java, SQL experience is not necessary",
                     "Java, SQL not preferred"):
            with self.subTest(text=text):
                result = extract_requirements(source_detail(job_content="Requirements\n" + text))
                self.assertEqual(classifications(result), {"Java": "unspecified", "SQL": "unspecified"})
                self.assertEqual(result["groups"], [])
        for heading in ("Not required", "Not necessary", "필수가 아님", "필수가 아닙니다", "요구하지 않음", "요구하지 않습니다"):
            result = extract_requirements(source_detail(job_content="Requirements\nJava\n[" + heading + "]\nSQL"))
            self.assertEqual(classifications(result), {"Java": "required", "SQL": "unspecified"})

    def test_group_and_independent_evidence_aggregate_without_erasing_either(self):
        detail = source_detail(job_content="Java or Kotlin required\nJava preferred\nResponsibilities\nJava\nJava required")
        result = extract_requirements(detail)
        self.assertEqual(classifications(result), {"Java": "required", "Kotlin": "unspecified"})
        java = next(s for s in result["skills"] if s["skill"] == "Java")
        self.assertEqual([e["requirement_type"] for e in java["evidence"]],
                         ["unspecified", "preferred", "responsibility", "required"])
        self.assertEqual(len(result["groups"]), 1)
        self.assertEqual(result["groups"][0]["requirement_type"], "required")
        self.assert_provenance(detail, result)

    def test_group_order_repetition_aliases_and_offsets_are_deterministic(self):
        text = "【Qualifications】\r\n • springboot or postgres required\r\n\r\n • springboot or postgres required\r\n**Preferred:**\r\n k8s and Docker preferred"
        detail = source_detail(job_content=text)
        before = copy.deepcopy(detail)
        result = extract_requirements(detail)
        self.assertEqual(result, extract_requirements(dict(reversed(list(detail.items())))))
        self.assertEqual(detail, before)
        self.assertEqual([g["relation"] for g in result["groups"]], ["any_of", "any_of", "all_of"])
        self.assertEqual(result["groups"][0]["skills"], ["PostgreSQL", "Spring Boot"])
        self.assertNotEqual(result["groups"][0]["evidence"]["evidence_start"], result["groups"][1]["evidence"]["evidence_start"])
        self.assert_provenance(detail, result)
        result["groups"][0]["evidence"]["evidence_text"] = "changed"
        self.assertNotEqual(result, extract_requirements(detail))

    def test_groups_do_not_introduce_new_global_quality_states(self):
        for text, expected in (("Java or Kotlin required", "requirements_extracted"),
                               ("Java/Kotlin 중 하나", "requirement_evidence_present_but_unclassified")):
            self.assertEqual(extract_requirements(source_detail(job_content=text))["quality_status"], expected)
        self.assertEqual(extract_requirements(None)["groups"], [])
        self.assertEqual(extract_requirements(source_detail())["groups"], [])

    def test_shared_list_rule_does_not_spread_independent_clause_cues(self):
        for text in ("Java required, Python", "Java 필수, Python", "Java required and Python mentioned"):
            result = extract_requirements(source_detail(job_content=text))
            self.assertEqual(classifications(result)["Python"], "unspecified")
            self.assertEqual(result["groups"], [])

    def test_qualification_and_wrapped_headings_do_not_make_prose_a_section(self):
        for text in ("Qualifications are discussed with Java teams", "**Preferred:** discussions about Java"):
            result = extract_requirements(source_detail(job_content=text + "\nSQL"))
            self.assertEqual(classifications(result)["SQL"], "unspecified")

    def test_keyword_alternatives_never_create_requirement_groups(self):
        result = extract_requirements(source_detail(keywords=["Java or Kotlin required", "SQL and Python preferred"]))
        self.assertEqual(result["groups"], [])
        self.assertTrue(all(s["requirement_type"] == "unspecified" for s in result["skills"]))


if __name__ == "__main__":
    unittest.main()
