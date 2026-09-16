"""Current taxonomy contracts; KD IDs are documented in TEST_BASELINE.md."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jobskillradar.skill_extractor import canonicalize_skills, extract_skills


# Independent expectations: do not derive these from the production dictionary.
SUPPORTED = [
    "Python", "SQL", "R", "Java", "Pandas", "NumPy", "Statistics", "A/B Test",
    "Excel", "Tableau", "Power BI", "Looker", "Plotly", "Spark", "Airflow",
    "Kafka", "Docker", "Kubernetes", "AWS", "GCP", "Azure", "MySQL",
    "PostgreSQL", "MongoDB", "Machine Learning", "Deep Learning", "NLP",
    "PyTorch", "TensorFlow", "Recommender System", "GA4",
]


class SkillExtractionTest(unittest.TestCase):
    def test_all_current_canonical_names_and_case_variants(self):
        for skill in SUPPORTED:
            for text in (skill, skill.lower(), skill.upper()):
                with self.subTest(skill=skill, text=text):
                    self.assertEqual(extract_skills(text), [skill])

    def test_english_and_korean_aliases(self):
        cases = {
            "파이썬": "Python", "쿼리": "SQL", "통계": "Statistics",
            "ab test": "A/B Test", "a-b test": "A/B Test", "ab테스트": "A/B Test",
            "a/b테스트": "A/B Test", "엑셀": "Excel", "태블로": "Tableau",
            "powerbi": "Power BI", "스파크": "Spark", "k8s": "Kubernetes",
            "amazon web services": "AWS", "google cloud": "GCP",
            "postgres": "PostgreSQL", "mongo db": "MongoDB",
            "머신러닝": "Machine Learning", "ml": "Machine Learning",
            "딥러닝": "Deep Learning", "자연어": "NLP", "파이토치": "PyTorch",
            "텐서플로": "TensorFlow", "추천시스템": "Recommender System",
            "추천 시스템": "Recommender System", "google analytics 4": "GA4",
        }
        for alias, canonical in cases.items():
            with self.subTest(alias=alias):
                self.assertEqual(extract_skills(alias), [canonical])
                self.assertEqual(canonicalize_skills([alias]), [canonical])

    def test_duplicates_across_title_and_description_count_once(self):
        self.assertEqual(extract_skills("SQL python", "파이썬 Python 쿼리 sql"), ["Python", "SQL"])

    def test_empty_none_and_no_arguments(self):
        self.assertEqual(extract_skills(), [])
        self.assertEqual(extract_skills(None, "", "  "), [])

    def test_allowed_punctuation_and_korean_particles(self):
        self.assertEqual(extract_skills("(Python), SQL; [Java]/R!"), ["Python", "SQL", "R", "Java"])
        self.assertEqual(extract_skills("SQL과 파이썬을 사용"), ["Python", "SQL"])

    def test_unrelated_latin_words_do_not_match(self):
        self.assertEqual(extract_skills("JavaScript NoSQL sparks airflowing html"), [])

    def test_current_restricted_boundaries(self):
        for value in ("Python3", "Python+", "Python#", ".Python", "Python."):
            with self.subTest(value=value):
                self.assertEqual(extract_skills(value), [])

    def test_output_order_is_taxonomy_order_not_text_order(self):
        self.assertEqual(extract_skills("SQL Java Python"), ["Python", "SQL", "Java"])

    def test_current_known_defect_korean_substring(self):
        """KD-03: institution name is treated as a statistics skill mention."""
        self.assertEqual(extract_skills("통계청"), ["Statistics"])

    @unittest.expectedFailure
    def test_kd01_sentence_final_period_should_allow_python(self):
        """KD-01 / Phase 3: punctuation boundary currently drops Python."""
        self.assertEqual(extract_skills("Experience with Python."), ["Python"])

    @unittest.expectedFailure
    def test_kd02_research_abbreviation_should_not_imply_r_language(self):
        """KD-02 / Phase 3: R&D is not evidence of R language knowledge."""
        self.assertEqual(extract_skills("R&D department"), [])


class CanonicalizationTest(unittest.TestCase):
    def test_deduplicates_aliases_and_preserves_first_canonical_order(self):
        self.assertEqual(canonicalize_skills(["sql", "파이썬", "SQL", "Python", "k8s"]),
                         ["SQL", "Python", "Kubernetes"])

    def test_trims_whitespace_and_ignores_empty_strings(self):
        self.assertEqual(canonicalize_skills([" ", "", "\tPYTHON\n", " powerbi "]),
                         ["Python", "Power BI"])

    def test_unknown_values_preserve_spelling_and_case(self):
        self.assertEqual(canonicalize_skills([" custom-tool ", "custom-tool", "CUSTOM-TOOL"]),
                         ["custom-tool", "CUSTOM-TOOL"])

    def test_requires_whole_value_match(self):
        self.assertEqual(canonicalize_skills(["Python developer", "SQL, Python"]),
                         ["Python developer", "SQL, Python"])

    def test_empty_iterable_and_generator(self):
        self.assertEqual(canonicalize_skills([]), [])
        self.assertEqual(canonicalize_skills(x for x in ["python", "파이썬"]), ["Python"])


if __name__ == "__main__":
    unittest.main()
