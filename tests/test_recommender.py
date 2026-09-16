import copy
import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jobskillradar.recommender import recommend_skills


class RecommendationTest(unittest.TestCase):
    def test_frequency_plus_foundation_scores_and_reasons(self):
        analysis = {"role_skill_counts": {"데이터 분석가": Counter({"Python": 5, "SQL": 2, "Kafka": 7})}}
        original = copy.deepcopy(analysis)
        result = recommend_skills("데이터 분석가", [], analysis)
        # Python 5+4=9; SQL 2+5=7; Kafka 7+0=7. SQL precedes Kafka on the tie.
        self.assertEqual([(r["skill"], r["score"]) for r in result],
                         [("Python", 9), ("SQL", 7), ("Kafka", 7), ("Statistics", 3), ("Pandas", 2), ("Tableau", 1)])
        self.assertEqual(result[0]["reason"], "목표 직무의 기초 역량으로 먼저 학습하기 좋습니다.")
        self.assertEqual(result[2]["reason"], "목표 직무 공고에서 자주 등장합니다.")
        self.assertEqual(analysis, original)

    def test_foundations_for_every_current_role_with_empty_analysis(self):
        cases = {
            "데이터 분석가": ["SQL", "Python", "Statistics", "Pandas", "Tableau"],
            "BI 분석가": ["SQL", "Power BI", "Tableau", "Excel", "Looker"],
            "데이터 엔지니어": ["SQL", "Python", "Spark", "Airflow", "AWS"],
            "ML 엔지니어": ["Python", "Machine Learning", "PyTorch", "Deep Learning", "SQL"],
        }
        for role, skills in cases.items():
            with self.subTest(role=role):
                self.assertEqual([(r["skill"], r["score"]) for r in recommend_skills(role, [], {})],
                                 list(zip(skills, [5, 4, 3, 2, 1])))

    def test_owned_aliases_are_excluded_before_limit(self):
        result = recommend_skills("데이터 분석가", [" sql ", "파이썬", "Python"], {}, limit=2)
        self.assertEqual([(r["skill"], r["score"]) for r in result], [("Statistics", 3), ("Pandas", 2)])

    def test_missing_and_empty_role_counts_fall_back_to_global(self):
        for role_counts in ({}, {"데이터 분석가": Counter()}):
            with self.subTest(role_counts=role_counts):
                result = recommend_skills("데이터 분석가", [], {
                    "role_skill_counts": role_counts, "skill_counts": Counter({"Kafka": 10}),
                })
                self.assertEqual(result[0], {"skill": "Kafka", "score": 10,
                                           "reason": "목표 직무 공고에서 자주 등장합니다."})

    def test_nonempty_role_counts_do_not_merge_global_counts(self):
        result = recommend_skills("데이터 분석가", [], {
            "role_skill_counts": {"데이터 분석가": Counter({"Python": 1})},
            "skill_counts": Counter({"Kafka": 100}),
        })
        self.assertNotIn("Kafka", [r["skill"] for r in result])

    def test_tie_order_follows_candidate_insertion_order(self):
        result = recommend_skills("unlisted role", [], {"skill_counts": Counter({"Java": 2, "SQL": 2})})
        self.assertEqual([r["skill"] for r in result], ["Java", "SQL"])

    def test_positive_limits_and_all_owned(self):
        self.assertEqual(len(recommend_skills("BI 분석가", [], {}, limit=1)), 1)
        self.assertEqual(len(recommend_skills("BI 분석가", [], {}, limit=100)), 5)
        self.assertEqual(recommend_skills("BI 분석가", ["SQL", "Power BI", "Tableau", "Excel", "Looker"], {}), [])

    def test_unknown_role_with_empty_analysis_has_no_candidates(self):
        self.assertEqual(recommend_skills("unlisted role", [], {}), [])

    def test_current_known_defect_nonpositive_limit_returns_one(self):
        """KD-05: stop condition is checked only after appending a result."""
        for limit in (0, -1):
            with self.subTest(limit=limit):
                self.assertEqual(len(recommend_skills("데이터 분석가", [], {}, limit)), 1)

    @unittest.expectedFailure
    def test_kd05_zero_limit_should_return_no_recommendations(self):
        """KD-05 / Phase 3 recommendation contract cleanup."""
        self.assertEqual(recommend_skills("데이터 분석가", [], {}, limit=0), [])


if __name__ == "__main__":
    unittest.main()
