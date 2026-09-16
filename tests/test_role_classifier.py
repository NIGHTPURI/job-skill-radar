"""Role evidence contracts, including ambiguous and insufficient evidence."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jobskillradar.analyzer import enrich_posting
from jobskillradar.role_classifier import classify_role


class RoleClassifierTest(unittest.TestCase):
    def assert_titles(self, titles, expected):
        for title in titles:
            with self.subTest(title=title):
                self.assertEqual(enrich_posting({"title": title})["role"], expected)

    def test_backend_titles(self):
        self.assert_titles(["Backend Engineer", "Back-end Developer", "Back End Engineer", "백엔드 개발자",
                            "백엔드개발자", "서버 개발자", "Server Developer", "Server-side Engineer",
                            "API developer"], "백엔드 엔지니어")

    def test_frontend_titles(self):
        self.assert_titles(["Frontend Engineer", "Front-end Developer", "Web Frontend Engineer",
                            "프론트엔드 개발자", "프론트엔드개발자", "UI developer"], "프론트엔드 엔지니어")

    def test_full_stack_titles(self):
        self.assert_titles(["Full-stack Engineer", "Full Stack Developer", "Fullstack Developer",
                            "풀스택 개발자", "풀스택개발자", "full-stack application"], "풀스택 엔지니어")

    def test_data_analyst_titles(self):
        self.assert_titles(["Data Analyst", "데이터 분석가", "신입 데이터 분석 담당자", "데이터분석가",
                            "Statistical Analysis", "공공데이터 분석 및 시각화 담당"], "데이터 분석가")

    def test_bi_titles(self):
        self.assert_titles(["BI Analyst", "Business Intelligence Analyst", "BI 개발자", "KPI analyst",
                            "BI 데이터 분석가", "BI Data Analyst"], "BI 분석가")

    def test_data_engineer_titles(self):
        self.assert_titles(["Data Engineer", "Data Platform Engineer", "Data Infrastructure Engineer",
                            "데이터 엔지니어", "데이터 플랫폼 엔지니어", "데이터엔지니어"], "데이터 엔지니어")

    def test_ml_ai_titles(self):
        self.assert_titles(["Machine Learning Engineer", "ML engineer", "AI Engineer", "AI/ML Engineer",
                            "머신러닝 엔지니어", "AI 엔지니어", "Deep Learning Engineer", "NLP Engineer",
                            "ML Platform Engineer", "AI 데이터 사이언티스트"], "ML 엔지니어")

    def test_devops_cloud_titles(self):
        self.assert_titles(["DevOps Engineer", "SRE", "Site Reliability Engineer", "Cloud Engineer",
                            "Platform Engineer", "Infrastructure Engineer", "클라우드 엔지니어",
                            "인프라 엔지니어", "플랫폼 엔지니어"], "DevOps / 클라우드 엔지니어")

    def test_unknown_titles(self):
        self.assert_titles(["", "Software Engineer", "Java Developer", "Specialist", "채용 공고",
                            "Mobile Developer", "Retail Assistant", "Email Administrator", "Server"], "미분류 / 기타")

    def test_explicit_titles_win_over_incidental_technology(self):
        cases = [
            ("Backend Engineer", "Docker AWS", "백엔드 엔지니어"),
            ("Data Engineer", "Docker Kubernetes", "데이터 엔지니어"),
            ("ML Engineer", "Java Spring Boot PyTorch", "ML 엔지니어"),
            ("DevOps Engineer", "Python SQL", "DevOps / 클라우드 엔지니어"),
            ("Frontend Engineer", "Tableau SQL", "프론트엔드 엔지니어"),
            ("Data Analyst", "Docker Kubernetes PyTorch Tableau", "데이터 분석가"),
        ]
        for title, description, role in cases:
            with self.subTest(title=title):
                self.assertEqual(enrich_posting({"title": title, "description": description})["role"], role)

    def test_strong_title_wins_over_other_responsibilities(self):
        self.assertEqual(classify_role({"title": "Backend Engineer", "description": "machine learning and ETL"},
                                       ["Airflow", "Kafka", "PyTorch"]), "백엔드 엔지니어")
        self.assertEqual(classify_role({"title": "Data Analyst", "description": "dashboard development"},
                                       ["Tableau", "SQL"]), "데이터 분석가")

    def test_responsibility_phrases_with_weak_title(self):
        cases = {
            "백엔드 엔지니어": ["Develop APIs for customers", "API 개발", "server-side development"],
            "프론트엔드 엔지니어": ["web UI development", "user interface development", "프론트엔드 개발"],
            "풀스택 엔지니어": ["full-stack development", "풀스택 개발"],
            "데이터 분석가": ["statistical analysis", "데이터 분석", "analytics"],
            "BI 분석가": ["dashboard development", "KPI reporting", "대시보드 운영"],
            "데이터 엔지니어": ["ETL 구축", "build data pipelines", "data warehouse", "데이터 레이크"],
            "ML 엔지니어": ["model training", "deep learning", "자연어 처리", "머신러닝 연구"],
            "DevOps / 클라우드 엔지니어": ["deployment automation", "cloud infrastructure", "운영 자동화"],
        }
        for role, descriptions in cases.items():
            for description in descriptions:
                with self.subTest(description=description):
                    self.assertEqual(classify_role({"title": "Specialist", "description": description}, []), role)

    def test_responsibilities_win_over_conflicting_skill_cluster(self):
        self.assertEqual(classify_role({"description": "API development"}, ["Spark", "SQL"]), "백엔드 엔지니어")

    def test_backend_skill_clusters(self):
        for skills in (["Java", "Spring Boot"], ["Spring", "Redis"], ["Kotlin", "JPA", "PostgreSQL"],
                       ["Spring Security", "Hibernate"], ["Java", "QueryDSL", "MySQL"]):
            with self.subTest(skills=skills):
                self.assertEqual(classify_role({}, skills), "백엔드 엔지니어")

    def test_data_engineering_skill_clusters(self):
        for skills in (["Airflow", "SQL"], ["Spark", "Kafka"], ["Airflow", "GCP"], ["Spark", "Airflow"]):
            with self.subTest(skills=skills):
                self.assertEqual(classify_role({}, skills), "데이터 엔지니어")

    def test_ml_skill_clusters(self):
        for skills in (["Python", "PyTorch"], ["NLP", "TensorFlow"], ["Machine Learning", "PyTorch"]):
            with self.subTest(skills=skills):
                self.assertEqual(classify_role({}, skills), "ML 엔지니어")

    def test_bi_and_analytics_skill_clusters(self):
        for skills, role in [(["Tableau", "SQL"], "BI 분석가"), (["Power BI", "Excel"], "BI 분석가"),
                             (["Looker", "SQL"], "BI 분석가"), (["Statistics", "Python"], "데이터 분석가"),
                             (["A/B Test", "SQL"], "데이터 분석가")]:
            with self.subTest(skills=skills):
                self.assertEqual(classify_role({}, skills), role)

    def test_devops_skill_clusters(self):
        for skills in (["Docker", "CI/CD", "AWS"], ["Kubernetes", "Jenkins", "Linux"],
                       ["Docker", "GitHub Actions", "Azure"]):
            with self.subTest(skills=skills):
                self.assertEqual(classify_role({}, skills), "DevOps / 클라우드 엔지니어")

    def test_single_skills_never_determine_a_role(self):
        for skill in ("Docker", "Kubernetes", "AWS", "Java", "SQL", "Python", "Kafka", "Spring Boot",
                      "Tableau", "PyTorch", "Airflow", "Statistics", "CI/CD", "JavaScript", "TypeScript"):
            with self.subTest(skill=skill):
                self.assertEqual(classify_role({}, [skill]), "미분류 / 기타")

    def test_incomplete_clusters_remain_unknown(self):
        for skills in (["Java", "JavaScript"], ["JavaScript", "TypeScript"], ["Docker", "AWS"],
                       ["Docker", "Kubernetes"], ["SQL", "Python"], ["Java", "Redis"],
                       ["Kotlin", "JPA"], ["Docker", "Jenkins"]):
            with self.subTest(skills=skills):
                self.assertEqual(classify_role({}, skills), "미분류 / 기타")

    def test_substring_negatives_in_both_fields(self):
        for text in ("mobile", "retail", "email", "chair", "domain", "bilingual", "html", "xml",
                     "detail", "hotel", "sales pipeline", "airline", "backendless", "my_backend",
                     "인프라레드", "데이터분석가족", "통계 분석표", "분석가", "server room"):
            for field in ("title", "description"):
                with self.subTest(text=text, field=field):
                    self.assertEqual(classify_role({field: text}, []), "미분류 / 기타")

    def test_case_punctuation_spacing_and_korean_boundaries(self):
        for title in ("[BACKEND ENGINEER]", "back\tend developer", "Back-End Engineer",
                      "백엔드개발자", "백엔드 개발자를 모집합니다"):
            with self.subTest(title=title):
                self.assertEqual(classify_role({"title": title}, []), "백엔드 엔지니어")

    def test_ambiguous_explicit_roles_return_unknown_not_first_match(self):
        for title in ("Backend Engineer / Data Engineer", "Data Engineer / Backend Engineer",
                      "Backend / Frontend", "Data Analyst / BI Analyst", "ML Engineer and SRE"):
            with self.subTest(title=title):
                self.assertEqual(classify_role({"title": title}, ["Spring Boot", "Java"]), "미분류 / 기타")

    def test_full_stack_explicitly_resolves_backend_frontend_combination(self):
        self.assertEqual(classify_role({"title": "Full-stack Backend / Frontend Engineer"}, []), "풀스택 엔지니어")
        self.assertEqual(classify_role({"title": "Full-stack / Data Engineer"}, []), "미분류 / 기타")

    def test_specific_compound_title_overrides_contained_general_role(self):
        cases = [("Data Platform Engineer", "데이터 엔지니어"), ("ML Platform Engineer", "ML 엔지니어"),
                 ("데이터 플랫폼 엔지니어", "데이터 엔지니어"), ("BI Data Analyst", "BI 분석가")]
        for title, role in cases:
            with self.subTest(title=title):
                self.assertEqual(classify_role({"title": title}, []), role)

    def test_backend_in_ml_platform_is_still_backend(self):
        for title in ("ML platform backend", "Backend engineer working on AI services"):
            with self.subTest(title=title):
                self.assertEqual(enrich_posting({"title": title, "description": "Kafka Airflow PyTorch"})["role"],
                                 "백엔드 엔지니어")

    def test_generic_ai_integration_is_not_ml_responsibility(self):
        self.assertEqual(enrich_posting({"title": "Software Developer", "description": "AI API integration"})["role"],
                         "미분류 / 기타")

    def test_conflicting_responsibilities_do_not_fall_through_to_skills(self):
        for description in ("API development and data pipelines", "data pipelines and API development"):
            with self.subTest(description=description):
                self.assertEqual(classify_role({"description": description}, ["Java", "Spring Boot"]), "미분류 / 기타")

    def test_conflicting_skill_clusters_return_unknown(self):
        skills = ["Spring Boot", "Java", "Airflow", "SQL"]
        self.assertEqual(classify_role({}, skills), "미분류 / 기타")
        self.assertEqual(classify_role({}, list(reversed(skills))), "미분류 / 기타")

    def test_duplicates_and_order_do_not_amplify_skill_evidence(self):
        self.assertEqual(classify_role({}, ["Docker"] * 20), "미분류 / 기타")
        self.assertEqual(classify_role({}, ["Java", "Spring Boot"]),
                         classify_role({}, ["Spring Boot", "Java", "Java"]))

    def test_missing_and_none_fields_are_unknown(self):
        for posting in ({}, {"title": None}, {"title": "", "description": None}, {"description": ""}):
            with self.subTest(posting=posting):
                self.assertEqual(classify_role(posting, []), "미분류 / 기타")

    def test_phrases_do_not_span_fields(self):
        self.assertEqual(classify_role({"title": "Data", "description": "Engineer"}, []), "미분류 / 기타")

    def test_career_metadata_does_not_affect_role(self):
        for career in (None, "", "경력무관", "신입", "경력"):
            with self.subTest(career=career):
                self.assertEqual(classify_role({"title": "Backend Engineer", "career": career}, []), "백엔드 엔지니어")
                self.assertEqual(classify_role({"career": career}, []), "미분류 / 기타")

    def test_input_is_not_mutated(self):
        posting = {"title": "Backend Engineer", "description": "AI integration", "career": "경력무관"}
        skills = ["Python", "Docker"]
        before = copy.deepcopy((posting, skills))
        classify_role(posting, skills)
        self.assertEqual((posting, skills), before)


if __name__ == "__main__":
    unittest.main()
