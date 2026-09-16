import copy
import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jobskillradar.analyzer import ROLE_LABELS, analyze_postings, classify_role, enrich_posting, top_items


class RoleClassificationTest(unittest.TestCase):
    def test_existing_labels(self):
        self.assertEqual(ROLE_LABELS, ["데이터 분석가", "데이터 엔지니어", "ML 엔지니어", "BI 분석가",
                                       "백엔드 엔지니어", "프론트엔드 엔지니어", "풀스택 엔지니어",
                                       "DevOps / 클라우드 엔지니어", "미분류 / 기타"])

    def test_title_rules_for_all_roles(self):
        for title, role in [("데이터 분석 담당", "데이터 분석가"),
                            ("데이터 엔지니어", "데이터 엔지니어"),
                            ("ML researcher", "ML 엔지니어"), ("KPI analyst", "BI 분석가")]:
            with self.subTest(title=title):
                self.assertEqual(classify_role({"title": title}, []), role)

    def test_description_rules(self):
        for description, role in [("ETL 구축", "데이터 엔지니어"),
                                  ("머신러닝 연구", "ML 엔지니어"),
                                  ("dashboard 운영", "BI 분석가")]:
            with self.subTest(description=description):
                self.assertEqual(classify_role({"title": "specialist", "description": description}, []), role)

    def test_skill_rules(self):
        groups = [("데이터 엔지니어", [["Spark", "SQL"], ["Airflow", "Kafka"]]),
                  ("ML 엔지니어", [["Machine Learning", "PyTorch"], ["Python", "TensorFlow"]]),
                  ("BI 분석가", [["Tableau", "SQL"], ["Power BI", "Excel"], ["Looker", "SQL"]])]
        for role, skills in groups:
            for cluster in skills:
                with self.subTest(cluster=cluster):
                    self.assertEqual(classify_role({}, cluster), role)

    def test_bi_title_precedes_analyst_and_ml(self):
        self.assertEqual(classify_role({"title": "BI 데이터 분석가", "description": "머신러닝"},
                                       ["PyTorch", "Docker"]), "BI 분석가")

    def test_analyst_title_precedes_engineering_and_ml(self):
        self.assertEqual(classify_role({"title": "데이터 분석가", "description": "파이프라인"},
                                       ["PyTorch", "Docker"]), "데이터 분석가")

    def test_platform_title_is_not_overridden_by_incidental_ml_skill(self):
        self.assertEqual(classify_role({"title": "플랫폼 엔지니어"}, ["PyTorch"]), "DevOps / 클라우드 엔지니어")

    def test_generic_platform_and_ai_mentions_are_insufficient(self):
        # classify_role consumes supplied skills; it does not extract them itself.
        self.assertEqual(classify_role({"description": "플랫폼 AI"}, []), "미분류 / 기타")

    def test_unknown_fallback_and_supported_english_roles(self):
        for title, role in [("", "미분류 / 기타"), ("specialist", "미분류 / 기타"),
                            ("Backend Engineer", "백엔드 엔지니어"), ("Frontend Developer", "프론트엔드 엔지니어"),
                            ("DevOps Engineer", "DevOps / 클라우드 엔지니어")]:
            with self.subTest(title=title):
                self.assertEqual(classify_role({"title": title}, []), role)

    def test_kd04_substrings_no_longer_misclassify_unrelated_titles(self):
        """KD-04 fixed: bounded phrases and explicit backend support."""
        self.assertEqual(classify_role({"title": "mobile developer"}, []), "미분류 / 기타")
        self.assertEqual(classify_role({"title": "retail assistant"}, []), "미분류 / 기타")
        self.assertEqual(classify_role({"title": "백엔드 엔지니어"}, []), "백엔드 엔지니어")


class AnalyzerTest(unittest.TestCase):
    def test_all_nine_roles_aggregate_with_deterministic_skill_counts(self):
        cases = [
            ("Backend Engineer", "백엔드 엔지니어"), ("Frontend Engineer", "프론트엔드 엔지니어"),
            ("Full-stack Engineer", "풀스택 엔지니어"), ("Data Analyst", "데이터 분석가"),
            ("BI Analyst", "BI 분석가"), ("Data Engineer", "데이터 엔지니어"),
            ("ML Engineer", "ML 엔지니어"), ("DevOps Engineer", "DevOps / 클라우드 엔지니어"),
            ("Specialist", "미분류 / 기타"),
        ]
        postings = [{"title": title, "description": "SQL SQL"} for title, _ in cases]
        result = analyze_postings(postings)
        self.assertEqual([posting["role"] for posting in result["postings"]], [role for _, role in cases])
        self.assertEqual(result["role_counts"], dict.fromkeys(ROLE_LABELS, 1))
        self.assertEqual(result["skill_counts"], {"SQL": 9, "Machine Learning": 1})
        expected = {role: {"SQL": 1} for role in ROLE_LABELS}
        expected["ML 엔지니어"]["Machine Learning"] = 1
        self.assertEqual(result["role_skill_counts"], expected)
        self.assertEqual(result, analyze_postings(postings))
        reversed_result = analyze_postings(list(reversed(postings)))
        self.assertEqual(result["role_counts"], reversed_result["role_counts"])
        self.assertEqual(result["role_skill_counts"], reversed_result["role_skill_counts"])

    def test_unknown_with_no_skills_retains_empty_role_skill_mapping(self):
        result = analyze_postings([{"title": None, "description": None}])
        self.assertEqual(result["postings"][0]["role"], "미분류 / 기타")
        self.assertEqual(result["role_counts"], {"미분류 / 기타": 1})
        self.assertEqual(result["role_skill_counts"], {})

    def test_empty_input(self):
        self.assertEqual(analyze_postings([]), {
            "postings": [], "skill_counts": Counter(), "role_counts": Counter(),
            "career_counts": Counter(), "region_counts": Counter(), "role_skill_counts": {},
        })

    def test_enrichment_preserves_fields_without_mutating_input(self):
        posting = {"title": "데이터 분석가", "description": "SQL Python SQL", "custom": "keep"}
        original = copy.deepcopy(posting)
        self.assertEqual(enrich_posting(posting), {
            **posting, "skills": ["Python", "SQL"], "role": "데이터 분석가",
        })
        self.assertEqual(posting, original)

    def test_single_posting_and_missing_optional_values(self):
        result = analyze_postings([{"title": "SQL specialist"}])
        self.assertEqual(result["postings"], [{"title": "SQL specialist", "skills": ["SQL"], "role": "미분류 / 기타"}])
        self.assertEqual(result["skill_counts"], {"SQL": 1})
        self.assertEqual(result["role_counts"], {"미분류 / 기타": 1})
        self.assertEqual(result["career_counts"], {"미상": 1})
        self.assertEqual(result["region_counts"], {"미상": 1})
        self.assertEqual(result["role_skill_counts"], {"미분류 / 기타": {"SQL": 1}})

    def test_multiple_postings_count_each_skill_once_per_posting(self):
        postings = [
            {"title": "데이터 분석가", "description": "SQL Python SQL", "career": "신입", "region": "서울"},
            {"title": "BI analyst", "description": "SQL Tableau", "career": "경력", "region": "서울"},
            {"title": "데이터 엔지니어", "description": "Python Kafka", "career": "경력", "region": "경기"},
        ]
        original = copy.deepcopy(postings)
        result = analyze_postings(postings)
        self.assertEqual(result["skill_counts"], {"Python": 2, "SQL": 2, "Tableau": 1, "Kafka": 1})
        self.assertEqual(result["role_counts"], {"데이터 분석가": 1, "BI 분석가": 1, "데이터 엔지니어": 1})
        self.assertEqual(result["career_counts"], {"신입": 1, "경력": 2})
        self.assertEqual(result["region_counts"], {"서울": 2, "경기": 1})
        self.assertEqual(result["role_skill_counts"], {
            "데이터 분석가": {"Python": 1, "SQL": 1}, "BI 분석가": {"SQL": 1, "Tableau": 1},
            "데이터 엔지니어": {"Python": 1, "Kafka": 1},
        })
        self.assertEqual(result, analyze_postings(postings))
        self.assertEqual(top_items(result["skill_counts"], 2), [("Python", 2), ("SQL", 2)])
        self.assertEqual(postings, original)

    def test_explicit_empty_and_none_metadata_are_not_normalized_here(self):
        result = analyze_postings([{"career": None, "region": ""}])
        self.assertEqual(result["career_counts"], {None: 1})
        self.assertEqual(result["region_counts"], {"": 1})
        self.assertEqual(result["role_skill_counts"], {})


if __name__ == "__main__":
    unittest.main()
