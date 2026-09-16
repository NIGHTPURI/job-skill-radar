import copy
import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jobskillradar.analyzer import analyze_postings
from jobskillradar.models import SkillRecommendation
from jobskillradar.recommender import ROLE_FOUNDATION, recommend_skills
from jobskillradar.role_classifier import (
    BACKEND, BI_ANALYST, DATA_ANALYST, DATA_ENGINEER, DEVOPS,
    FRONTEND, FULL_STACK, ML_ENGINEER, ROLE_LABELS, UNKNOWN,
)
from jobskillradar.skill_taxonomy import SKILL_DEFINITIONS


class RecommendationTest(unittest.TestCase):
    def test_all_known_roles_use_only_their_own_market_evidence(self):
        cases = [
            (BACKEND, "Backend Engineer", "Spring Boot"),
            (FRONTEND, "Frontend Engineer", "TypeScript"),
            (FULL_STACK, "Full-stack Engineer", "JavaScript"),
            (DATA_ANALYST, "Data Analyst", "Pandas"),
            (BI_ANALYST, "BI Analyst", "Power BI"),
            (DATA_ENGINEER, "Data Engineer", "Airflow"),
            (ML_ENGINEER, "AI Engineer", "PyTorch"),
            (DEVOPS, "DevOps Engineer", "Kubernetes"),
        ]
        analysis = analyze_postings([
            {"title": title, "description": skill} for _, title, skill in cases
        ] + [{"title": "Specialist", "description": "Oracle"}] * 20)
        for role, _, skill in cases:
            with self.subTest(role=role):
                result = recommend_skills(role, [], analysis, 100)
                self.assertEqual([(r["skill"], r["market_count"]) for r in result if r["market_count"]],
                                 [(skill, 1)])
                self.assertEqual(result[0]["skill"], skill)
                self.assertTrue(all(r["role_posting_count"] == 1 for r in result))
                self.assertNotIn("Oracle", [r["skill"] for r in result])

    def test_backend_is_not_driven_by_ml_or_bi_postings(self):
        analysis = analyze_postings([
            {"title": "Backend Engineer", "description": "Java Spring Boot"},
        ] + [{"title": "AI Engineer", "description": "PyTorch"}] * 10
          + [{"title": "BI Analyst", "description": "Tableau"}] * 10)
        result = recommend_skills(BACKEND, [], analysis)
        self.assertEqual([r["skill"] for r in result], ["Java", "Spring Boot", "Git", "REST API", "SQL"])

    def test_foundations_are_small_canonical_and_cover_exactly_known_roles(self):
        expected = {
            BACKEND: {"Git", "REST API", "SQL"},
            FRONTEND: {"Git", "JavaScript"},
            FULL_STACK: {"Git", "JavaScript", "REST API", "SQL"},
            DATA_ANALYST: {"Python", "SQL", "Statistics"},
            BI_ANALYST: {"Excel", "SQL", "Statistics"},
            DATA_ENGINEER: {"Git", "Python", "SQL"},
            ML_ENGINEER: {"Machine Learning", "Python", "Statistics"},
            DEVOPS: {"CI/CD", "Git", "Linux"},
        }
        self.assertEqual(set(ROLE_FOUNDATION), set(ROLE_LABELS) - {UNKNOWN})
        for role, skills in expected.items():
            with self.subTest(role=role):
                self.assertEqual(set(ROLE_FOUNDATION[role]), skills)
                self.assertTrue(skills <= SKILL_DEFINITIONS.keys())
                result = recommend_skills(role, [], analyze_postings([]))
                self.assertEqual([r["skill"] for r in result], sorted(skills, key=str.casefold))
                self.assertTrue(all(r["is_foundation"] and r["market_count"] == 0 for r in result))

    def test_missing_role_uses_foundations_without_global_fallback(self):
        analysis = analyze_postings([{"title": "AI Engineer", "description": "PyTorch"}])
        result = recommend_skills(BACKEND, [], analysis)
        self.assertEqual([r["skill"] for r in result], ["Git", "REST API", "SQL"])
        for item in result:
            self.assertEqual(item["evidence_source"], "foundation_only")
            self.assertEqual(item["role_posting_count"], 0)
            self.assertIn("공고가 없어", item["reason"])

    def test_role_with_postings_but_no_extracted_skills_is_not_no_postings(self):
        analysis = analyze_postings([{"title": "Backend Engineer"}, {"title": "Backend Engineer"}])
        result = recommend_skills(BACKEND, [], analysis)
        for item in result:
            self.assertEqual((item["market_count"], item["role_posting_count"]), (0, 2))
            self.assertEqual(item["evidence_source"], "foundation_only")
            self.assertIn("2건에서 이 기술의 언급은 추출되지 않아", item["reason"])
            self.assertNotIn("공고가 없어", item["reason"])

    def test_missing_and_empty_role_skill_mappings_never_use_global_counts(self):
        for role_skills in ({}, {BACKEND: Counter()}):
            with self.subTest(role_skills=role_skills):
                result = recommend_skills(BACKEND, [], {
                    "role_skill_counts": role_skills, "skill_counts": Counter({"PyTorch": 100}),
                })
                self.assertEqual([r["skill"] for r in result], ["Git", "REST API", "SQL"])
                self.assertTrue(all(r["market_count"] == 0 for r in result))

    def test_unknown_and_unsupported_roles_have_no_recommendations(self):
        analysis = analyze_postings([{"title": "Specialist", "description": "SQL Python"}])
        for role in (UNKNOWN, "unlisted role", "", "Backend Engineer"):
            with self.subTest(role=role):
                self.assertEqual(recommend_skills(role, [], analysis), [])
                self.assertEqual(recommend_skills(role, [], {}), [])

    def test_owned_aliases_exclude_canonical_skills_and_duplicates(self):
        analysis = analyze_postings([{
            "title": "Backend Engineer", "description": "Spring Boot PostgreSQL Kubernetes Redis Git",
        }])
        owned = ["springboot", "Spring Boot", "postgres", "PostgreSQL", "k8s", "Kubernetes", "깃", "Git"]
        result = recommend_skills(BACKEND, owned, analysis, 100)
        self.assertEqual([r["skill"] for r in result], ["Redis", "REST API", "SQL"])
        self.assertEqual(result, recommend_skills(BACKEND, list(reversed(owned)), analysis, 100))

    def test_owned_foundation_aliases_are_excluded_before_limit(self):
        result = recommend_skills(DATA_ANALYST, [" sql ", "파이썬", "Python"], {}, 1)
        self.assertEqual([r["skill"] for r in result], ["Statistics"])
        self.assertEqual(result[0]["priority"], 1)

    def test_all_owned_returns_empty(self):
        self.assertEqual(recommend_skills(BACKEND, ["Git", "REST API", "SQL"], {}), [])

    def test_kd05_zero_limit_should_return_no_recommendations(self):
        """KD-05 fixed: non-positive limits do not append a candidate."""
        self.assertEqual(recommend_skills(DATA_ANALYST, [], {}, limit=0), [])

    def test_negative_limits_return_empty_with_or_without_market_data(self):
        for analysis in ({}, analyze_postings([{"title": "Backend Engineer", "description": "Java"}])):
            for limit in (-1, -20):
                with self.subTest(analysis=analysis, limit=limit):
                    self.assertEqual(recommend_skills(BACKEND, [], analysis, limit), [])

    def test_positive_limits_one_normal_and_above_candidate_count(self):
        for limit, expected in ((1, 1), (2, 2), (8, 3), (100, 3)):
            with self.subTest(limit=limit):
                result = recommend_skills(BACKEND, [], {}, limit)
                self.assertEqual(len(result), expected)
                self.assertEqual([r["priority"] for r in result], list(range(1, expected + 1)))

    def test_market_count_outranks_foundations_without_bonus(self):
        analysis = {"role_skill_counts": {DATA_ANALYST: Counter({"Kafka": 7, "Python": 5, "SQL": 2})}}
        result = recommend_skills(DATA_ANALYST, [], analysis)
        self.assertEqual([(r["skill"], r["market_count"]) for r in result],
                         [("Kafka", 7), ("Python", 5), ("SQL", 2), ("Statistics", 0)])

    def test_foundation_breaks_equal_market_count_tie(self):
        analysis = {"role_skill_counts": {BACKEND: Counter({"AWS": 1, "Git": 1, "Java": 2})}}
        self.assertEqual([r["skill"] for r in recommend_skills(BACKEND, [], analysis)],
                         ["Java", "Git", "AWS", "REST API", "SQL"])

    def test_canonical_name_breaks_ties_independently_of_insertion_order(self):
        expected = ["AWS", "Java", "Redis", "Git", "REST API", "SQL"]
        for skills in (["Redis", "Java", "AWS"], ["AWS", "Java", "Redis"]):
            analysis = {"role_skill_counts": {BACKEND: Counter(dict.fromkeys(skills, 2))}}
            for _ in range(5):
                self.assertEqual([r["skill"] for r in recommend_skills(BACKEND, [], analysis)], expected)

    def test_posting_order_does_not_change_results(self):
        postings = [{"title": "Backend Engineer", "description": skill} for skill in ("Java", "Redis", "Git")]
        self.assertEqual(recommend_skills(BACKEND, [], analyze_postings(postings)),
                         recommend_skills(BACKEND, [], analyze_postings(list(reversed(postings)))))

    def test_market_and_foundation_reasons_describe_both_sources(self):
        analysis = analyze_postings([{"title": "Backend Engineer", "description": "Git Java"}])
        result = {r["skill"]: r for r in recommend_skills(BACKEND, [], analysis)}
        self.assertEqual(result["Git"]["reason"],
                         "현재 분석한 백엔드 엔지니어 공고 1건 중 1건에서 언급되었습니다. 역할 기초 학습 후보이기도 합니다.")
        self.assertEqual(result["Java"]["reason"], "현재 분석한 백엔드 엔지니어 공고 1건 중 1건에서 언급되었습니다.")
        self.assertTrue(result["Git"]["is_foundation"])
        self.assertFalse(result["Java"]["is_foundation"])
        self.assertEqual(result["Git"]["evidence_source"], "role_market")
        self.assertEqual(result["Java"]["evidence_source"], "role_market")
        self.assertEqual(result["SQL"]["evidence_source"], "foundation_only")
        self.assertIn("언급은 추출되지 않아", result["SQL"]["reason"])

    def test_denominator_is_role_postings_including_postings_without_skills(self):
        analysis = analyze_postings([
            {"title": "Backend Engineer", "description": "Java Java SQL Git"},
            {"title": "Backend Engineer"},
            {"title": "Backend Engineer", "description": "Java"},
            {"title": "BI Analyst", "description": "Java SQL"},
        ])
        result = recommend_skills(BACKEND, [], analysis)
        self.assertEqual((result[0]["skill"], result[0]["market_count"], result[0]["role_posting_count"]),
                         ("Java", 2, 3))
        self.assertIn("공고 3건 중 2건", result[0]["reason"])

    def test_zero_denominator_has_no_ratios_or_market_evidence(self):
        for item in recommend_skills(BACKEND, [], analyze_postings([])):
            self.assertEqual((item["market_count"], item["role_posting_count"]), (0, 0))
            self.assertNotIn("%", item["reason"])
            self.assertNotIn("ratio", item)

    def test_partial_counts_do_not_invent_a_denominator(self):
        result = recommend_skills(BACKEND, [], {"role_skill_counts": {BACKEND: Counter({"Java": 2})}})
        self.assertIsNone(result[0]["role_posting_count"])
        self.assertIn("공고 2건에서 언급", result[0]["reason"])
        self.assertIn("전체 역할 공고 수는 제공되지 않았습니다", result[0]["reason"])
        self.assertIn("공고 수가 제공되지 않았고", result[1]["reason"])

    def test_result_contract_has_no_synthetic_score(self):
        result = recommend_skills(BACKEND, [], {})
        fields = {"skill", "priority", "market_count", "role_posting_count", "is_foundation", "evidence_source", "reason"}
        self.assertEqual(set(SkillRecommendation.__annotations__), fields)
        for item in result:
            self.assertEqual(set(item), fields)
            self.assertNotIn("score", item)

    def test_inputs_are_not_mutated(self):
        analysis = analyze_postings([{"title": "Backend Engineer", "description": "Java SQL"}])
        owned = [" sql ", "SQL"]
        original = copy.deepcopy((analysis, owned, ROLE_FOUNDATION))
        recommend_skills(BACKEND, owned, analysis)
        self.assertEqual((analysis, owned, ROLE_FOUNDATION), original)

    def test_career_metadata_does_not_affect_recommendations(self):
        results = [recommend_skills(BACKEND, [], analyze_postings([
            {"title": "Backend Engineer", "description": "Java SQL", "career": career},
        ])) for career in ("경력무관", "경력", "신입", None)]
        self.assertTrue(all(result == results[0] for result in results))


if __name__ == "__main__":
    unittest.main()
