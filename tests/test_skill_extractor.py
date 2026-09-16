"""Current taxonomy contracts; KD IDs are documented in TEST_BASELINE.md."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jobskillradar.skill_extractor import canonicalize_skills, extract_skills
from jobskillradar.skill_taxonomy import SKILL_DEFINITIONS


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
        self.assertEqual(extract_skills("JavaScript NoSQL sparks airflowing html"), ["JavaScript"])

    def test_current_restricted_boundaries(self):
        for value in ("Python3", "Python+", "Python#", "Pythonic", "_Python", "Python_tool"):
            with self.subTest(value=value):
                self.assertEqual(extract_skills(value), [])

    def test_output_order_is_taxonomy_order_not_text_order(self):
        self.assertEqual(extract_skills("SQL Java Python"), ["Python", "SQL", "Java"])

    def test_kd03_korean_institution_is_not_statistics(self):
        """KD-03 fixed: an institution name is not a skill mention."""
        self.assertEqual(extract_skills("통계청"), [])

    def test_kd01_sentence_final_period_should_allow_python(self):
        """KD-01 fixed: a sentence-final period is a delimiter."""
        self.assertEqual(extract_skills("Experience with Python."), ["Python"])

    def test_kd02_research_abbreviation_should_not_imply_r_language(self):
        """KD-02 fixed: R&D is not evidence of R language knowledge."""
        self.assertEqual(extract_skills("R&D department"), [])


class CanonicalizationTest(unittest.TestCase):
    def test_new_aliases_and_specific_concepts_preserve_input_order(self):
        self.assertEqual(canonicalize_skills([
            " 스프링부트 ", "SPRINGBOOT", "Spring", "spring security", "스프링시큐리티",
            "postgres", "PostgreSQL", "깃", "Git", "k8s", " custom  tool ", "custom  tool",
        ]), ["Spring Boot", "Spring", "Spring Security", "PostgreSQL", "Git", "Kubernetes", "custom  tool"])

    def test_internal_whitespace_in_known_aliases(self):
        self.assertEqual(canonicalize_skills([" Spring\t BOOT ", "spring\nboot", "REST   API", "ci / cd"]),
                         ["Spring Boot", "REST API", "CI/CD"])

    def test_whole_name_input_does_not_use_extraction_context(self):
        self.assertEqual(canonicalize_skills(["r", "R&D", "10 ml", "Go", "AI", "C"]),
                         ["R", "R&D", "10 ml", "Go", "AI", "C"])

    def test_canonicalization_is_idempotent(self):
        first = canonicalize_skills(["SpringBoot", "깃", " custom ", "CUSTOM", "postgres"])
        self.assertEqual(canonicalize_skills(first), first)

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


class SoftwareSkillExtractionTest(unittest.TestCase):
    def test_required_backend_canonical_names(self):
        required = [
            "Java", "Kotlin", "Python", "JavaScript", "TypeScript", "Spring", "Spring Boot",
            "Spring MVC", "Spring Security", "JPA", "Hibernate", "QueryDSL", "Gradle", "Maven",
            "MySQL", "PostgreSQL", "MariaDB", "Oracle", "Redis", "MongoDB", "Elasticsearch",
            "Kafka", "RabbitMQ", "Docker", "Kubernetes", "AWS", "GCP", "Azure", "Linux",
            "REST API", "GraphQL", "JWT", "OAuth", "Git", "GitHub Actions", "Jenkins", "CI/CD",
            "JUnit", "Mockito",
        ]
        for name in required:
            for text in (name, name.lower(), name.upper()):
                with self.subTest(name=name, text=text):
                    self.assertEqual(extract_skills(text), [name])
                    self.assertEqual(canonicalize_skills([text]), [name])

    def test_backend_posting_with_multiple_categories(self):
        text = (
            "Java/Kotlin, Spring Boot and Spring Security; JPA, Hibernate, QueryDSL. "
            "MySQL/PostgreSQL, Redis, Kafka, Docker/Kubernetes on AWS. "
            "Gradle, CI/CD, GitHub Actions, JUnit and Mockito."
        )
        self.assertEqual(extract_skills(text), [
            "Java", "Kafka", "Docker", "Kubernetes", "AWS", "MySQL", "PostgreSQL",
            "Kotlin", "Spring Boot", "Spring Security", "JPA", "Hibernate", "QueryDSL",
            "Gradle", "Redis", "GitHub Actions", "CI/CD", "JUnit", "Mockito",
        ])

    def test_explicit_english_aliases(self):
        cases = {
            "SpringBoot": "Spring Boot", "spring-boot": "Spring Boot", "springmvc": "Spring MVC",
            "springsecurity": "Spring Security", "java persistence api": "JPA",
            "jakarta persistence api": "JPA", "query dsl": "QueryDSL", "maria db": "MariaDB",
            "oracle database": "Oracle", "elastic search": "Elasticsearch", "rabbit mq": "RabbitMQ",
            "RESTful API": "REST API", "restapi": "REST API", "graph ql": "GraphQL",
            "json web token": "JWT", "OAuth2.0": "OAuth", "OAuth 2.0": "OAuth",
            "github-actions": "GitHub Actions", "ci-cd": "CI/CD", "ci / cd": "CI/CD",
            "JUnit5": "JUnit", "junit 4": "JUnit", "google cloud platform": "GCP",
        }
        for alias, name in cases.items():
            with self.subTest(alias=alias):
                self.assertEqual(extract_skills(alias), [name])
                self.assertEqual(canonicalize_skills([alias]), [name])

    def test_explicit_korean_aliases(self):
        cases = {
            "자바": "Java", "코틀린": "Kotlin", "자바스크립트": "JavaScript",
            "타입스크립트": "TypeScript", "스프링": "Spring", "스프링부트": "Spring Boot",
            "스프링 부트": "Spring Boot", "스프링 MVC": "Spring MVC",
            "스프링시큐리티": "Spring Security", "하이버네이트": "Hibernate",
            "쿼리DSL": "QueryDSL", "그래들": "Gradle", "메이븐": "Maven",
            "오라클": "Oracle", "레디스": "Redis", "카프카": "Kafka",
            "도커": "Docker", "쿠버네티스": "Kubernetes", "리눅스": "Linux",
            "깃": "Git", "깃허브 액션": "GitHub Actions", "젠킨스": "Jenkins",
            "자연어처리": "NLP", "텐서플로우": "TensorFlow", "통계분석": "Statistics",
        }
        for alias, name in cases.items():
            with self.subTest(alias=alias):
                self.assertEqual(extract_skills(alias), [name])
                self.assertEqual(canonicalize_skills([alias]), [name])

    def test_required_punctuation_boundaries(self):
        cases = [
            ("Python.", ["Python"]), ("Java,", ["Java"]), ("(Spring Boot)", ["Spring Boot"]),
            ("Kafka/Redis", ["Kafka", "Redis"]), ("AWS·Docker", ["Docker", "AWS"]),
            ("MySQL; PostgreSQL", ["MySQL", "PostgreSQL"]),
            ("Java\nKotlin\r\nPython", ["Python", "Java", "Kotlin"]),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(extract_skills(text), expected)

    def test_quotes_brackets_and_sentence_dots(self):
        for text in ('"Python"', "'Python'", "[Python]", "{Python}", "<Python>",
                     ".Python", "Python...", "Python: required", "Python?", "Python—Java"):
            with self.subTest(text=text):
                self.assertIn("Python", extract_skills(text))

    def test_whitespace_variants_of_multiword_aliases(self):
        self.assertEqual(extract_skills("Spring\tBoot; Machine\nLearning; REST   API"),
                         ["Machine Learning", "Spring Boot", "REST API"])

    def test_punctuation_does_not_join_separate_words(self):
        self.assertEqual(extract_skills("Machine, Learning; REST/API; GitHub/Actions"), [])

    def test_aliases_do_not_span_input_fields(self):
        self.assertEqual(extract_skills("Machine", "Learning"), [])
        self.assertEqual(extract_skills("Spring", "Boot"), ["Spring"])

    def test_identifiers_and_larger_words_do_not_match(self):
        for text in ("NoSQL", "JavaScripting", "preJava", "postgreSQLish", "gitlab", "github",
                     "RedisCache", "springboard", "springboots", "AWS_ACCOUNT", "my_python", "éPython"):
            with self.subTest(text=text):
                self.assertEqual(extract_skills(text), [])

    def test_short_aliases_do_not_match_inside_words(self):
        self.assertEqual(extract_skills("research XML HTML YAML R2 mr_r MLOps formal retailer"), [])

    def test_short_aliases_reject_ampersand_compounds(self):
        for text in ("R&D", "R & D", "r&d", "D&R", "HR&R", "ML & ops", "ops & ML"):
            with self.subTest(text=text):
                self.assertEqual(extract_skills(text), [])

    def test_short_aliases_reject_quantities(self):
        for text in ("10 ml", "10ml", "2.5 ML", "100\tml"):
            with self.subTest(text=text):
                self.assertEqual(extract_skills(text), [])

    def test_short_aliases_still_match_explicit_mentions(self):
        for text in ("R", "r", "(R)", "R.", "R/Python", "R을 사용", "R 4.3"):
            with self.subTest(text=text):
                self.assertIn("R", extract_skills(text))
        for text in ("ML", "ml", "ML engineer", "ML/Python", "ML을 활용"):
            with self.subTest(text=text):
                self.assertIn("Machine Learning", extract_skills(text))
        self.assertEqual(extract_skills("R&D; R and ML"), ["R", "Machine Learning"])

    def test_unsupported_ambiguous_short_names_are_not_inferred(self):
        self.assertEqual(extract_skills("C C++ C# Go go ahead AI retail said cargo"), [])
        self.assertEqual(canonicalize_skills(["C", "Go", "AI"]), ["C", "Go", "AI"])

    def test_korean_particles_require_a_complete_suffix(self):
        for text, expected in [
            ("파이썬으로 개발", ["Python"]), ("SQL과 Java를 사용", ["SQL", "Java"]),
            ("스프링부트와 레디스", ["Spring Boot", "Redis"]),
            ("깃을 사용", ["Git"]), ("통계를 분석", ["Statistics"]),
            ("Kotlin에서 TypeScript까지", ["Kotlin", "TypeScript"]),
        ]:
            with self.subTest(text=text):
                self.assertEqual(extract_skills(text), expected)

    def test_korean_unrelated_prefixes_suffixes_and_particle_prefixes(self):
        for text in ("통계청", "통계청에서", "통계로봇", "통계가족", "집계통계", "깃발", "깃털",
                     "깃허브", "자바라", "SQL과제", "Python으로봇", "스프링클러", "엑셀러레이터"):
            with self.subTest(text=text):
                self.assertEqual(extract_skills(text), [])

    def test_specific_mentions_do_not_imply_broader_skills(self):
        for name in ("Spring Boot", "Spring Security", "Spring MVC", "Machine Learning",
                     "Deep Learning", "REST API", "GitHub Actions", "JavaScript", "JPA"):
            with self.subTest(name=name):
                self.assertEqual(extract_skills(name), [name])
        self.assertEqual(extract_skills("Java Persistence API"), ["JPA"])

    def test_separate_broader_mentions_survive_overlap_suppression(self):
        self.assertEqual(extract_skills("Spring Boot; Spring; Spring Security; Spring Boot"),
                         ["Spring", "Spring Boot", "Spring Security"])
        self.assertEqual(extract_skills("GitHub Actions with Git; Java Persistence API and Java"),
                         ["Java", "JPA", "Git", "GitHub Actions"])

    def test_longer_alias_same_concept_and_repeated_aliases(self):
        self.assertEqual(extract_skills("Google Cloud Platform, GCP, Google Cloud; Oracle Database; Oracle"),
                         ["GCP", "Oracle"])

    def test_order_is_stable_across_input_order_and_repetitions(self):
        names = ["Redis", "Spring Boot", "Java", "GitHub Actions", "Python"]
        expected = ["Python", "Java", "Spring Boot", "Redis", "GitHub Actions"]
        for texts in (names, list(reversed(names)), names * 3):
            with self.subTest(texts=texts):
                self.assertEqual(extract_skills(*texts), expected)

    def test_taxonomy_alias_ownership_and_round_trip(self):
        owners = {}
        for canonical, (category, aliases) in SKILL_DEFINITIONS.items():
            self.assertTrue(category)
            for alias in (canonical, *aliases):
                key = " ".join(alias.casefold().split())
                with self.subTest(alias=alias):
                    self.assertTrue(key)
                    self.assertEqual(owners.setdefault(key, canonical), canonical)
                    self.assertEqual(canonicalize_skills([alias]), [canonical])
                    self.assertEqual(extract_skills(alias), [canonical])


if __name__ == "__main__":
    unittest.main()
