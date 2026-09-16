"""Deterministic role rules: explicit titles, responsibilities, skill clusters.

No numeric confidence or technology voting. Conflicting evidence at the winning
tier returns Unknown, except explicit full-stack covering backend/frontend.
"""
from __future__ import annotations

import re


DATA_ANALYST = "데이터 분석가"
DATA_ENGINEER = "데이터 엔지니어"
ML_ENGINEER = "ML 엔지니어"
BI_ANALYST = "BI 분석가"
BACKEND = "백엔드 엔지니어"
FRONTEND = "프론트엔드 엔지니어"
FULL_STACK = "풀스택 엔지니어"
DEVOPS = "DevOps / 클라우드 엔지니어"
UNKNOWN = "미분류 / 기타"

# Retain existing UI defaults and recommendation keys. Order is not precedence.
ROLE_LABELS = [DATA_ANALYST, DATA_ENGINEER, ML_ENGINEER, BI_ANALYST,
               BACKEND, FRONTEND, FULL_STACK, DEVOPS, UNKNOWN]

TITLE_PHRASES = {
    BACKEND: (
        "backend", "back end", "백엔드", "백엔드 개발자", "백엔드 엔지니어",
        "server developer", "server engineer", "server side developer", "server side engineer",
        "서버 개발자", "서버 개발", "서버 엔지니어", "api developer", "api engineer",
    ),
    FRONTEND: (
        "frontend", "front end", "프론트엔드", "프론트엔드 개발자", "프론트엔드 엔지니어",
        "ui developer", "ui engineer", "ui 개발자",
    ),
    FULL_STACK: ("full stack", "fullstack", "풀스택", "풀스택 개발자", "풀스택 엔지니어"),
    DATA_ANALYST: ("data analyst", "데이터 분석가", "데이터 분석 담당", "데이터 분석 담당자"),
    BI_ANALYST: (
        "bi analyst", "bi developer", "bi engineer", "bi 분석가", "bi 개발자", "kpi analyst",
        "business intelligence analyst", "business intelligence developer",
        "bi data analyst", "bi 데이터 분석가", "business intelligence data analyst",
    ),
    DATA_ENGINEER: (
        "data engineer", "data platform engineer", "data infrastructure engineer",
        "데이터 엔지니어", "데이터 플랫폼 엔지니어", "데이터 인프라 엔지니어",
    ),
    ML_ENGINEER: (
        "machine learning engineer", "machine learning researcher", "ml engineer", "ml researcher",
        "ai engineer", "ai researcher", "deep learning engineer", "nlp engineer", "nlp researcher",
        "ml platform engineer", "ai platform engineer", "머신러닝 엔지니어", "머신러닝 연구원",
        "ai 엔지니어", "ml 엔지니어", "딥러닝 엔지니어", "nlp 엔지니어",
        "data scientist", "데이터 사이언티스트",
    ),
    DEVOPS: (
        "devops", "sre", "site reliability engineer", "cloud engineer", "platform engineer",
        "infrastructure engineer", "클라우드 엔지니어", "플랫폼 엔지니어", "인프라 엔지니어",
        "데브옵스", "데브옵스 엔지니어",
    ),
}

RESPONSIBILITY_PHRASES = {
    BACKEND: (
        "backend development", "backend services", "server side development", "api development",
        "develop apis", "build apis", "백엔드 개발", "서버 개발", "api 개발", "api 구현",
    ),
    FRONTEND: (
        "frontend development", "front end development", "web ui development",
        "user interface development", "프론트엔드 개발", "ui 개발", "사용자 인터페이스 개발",
    ),
    FULL_STACK: ("full stack development", "fullstack development", "풀스택 개발"),
    DATA_ANALYST: (
        "data analysis", "statistical analysis", "analytics", "데이터 분석", "공공데이터 분석", "통계 분석",
    ),
    BI_ANALYST: (
        "business intelligence", "dashboard development", "build dashboards", "dashboard 운영",
        "kpi analysis", "kpi reporting", "bi reporting", "대시보드 개발", "대시보드 제작", "대시보드 운영",
    ),
    DATA_ENGINEER: (
        "data pipeline", "data pipelines", "data platform", "data warehouse", "data lake", "etl", "elt",
        "데이터 파이프라인", "데이터 플랫폼", "데이터 웨어하우스", "데이터 레이크",
    ),
    ML_ENGINEER: (
        "machine learning", "deep learning", "model training", "train models", "nlp development",
        "머신러닝 연구", "머신러닝 개발", "딥러닝 연구", "딥러닝 개발", "nlp 연구", "nlp 개발",
        "자연어 처리", "모델 학습", "추천 모델 개발", "추천 시스템 개발",
    ),
    DEVOPS: (
        "cloud infrastructure", "infrastructure automation", "deployment automation",
        "site reliability", "운영 자동화", "배포 자동화", "인프라 운영", "클라우드 운영",
    ),
}


def _phrase_pattern(phrase: str) -> re.Pattern[str]:
    words = phrase.casefold().split()
    pattern = re.escape(words[0])
    for previous, word in zip(words, words[1:]):
        # Korean job titles commonly omit spaces; English needs separators.
        korean_join = any("가" <= char <= "힣" for char in (previous[-1], word[0]))
        pattern += (r"\s*" if korean_join else r"[\s-]+") + re.escape(word)
    return re.compile(rf"(?<!\w){pattern}(?=(?:은|는|이|가|을|를|의|와|과)?(?!\w))")


def _compile_rules(phrases: dict[str, tuple[str, ...]]) -> list[tuple[str, re.Pattern[str]]]:
    return [(role, _phrase_pattern(phrase)) for role, values in phrases.items() for phrase in values]


_TITLE_RULES = _compile_rules(TITLE_PHRASES)
_RESPONSIBILITY_RULES = _compile_rules(RESPONSIBILITY_PHRASES)


def _text_roles(text: str, rules: list[tuple[str, re.Pattern[str]]]) -> set[str]:
    matches = [(match.start(), match.end(), role)
               for role, pattern in rules for match in pattern.finditer(text)]
    # A specific compound such as "data platform engineer" subsumes its inner
    # "platform engineer" phrase, not an unrelated role elsewhere in the text.
    return {role for start, end, role in matches
            if not any(left <= start and end <= right and right - left > end - start
                       for left, right, _ in matches)}


def _resolve(roles: set[str]) -> str | None:
    if not roles:
        return None
    if len(roles) == 1:
        return next(iter(roles))
    if FULL_STACK in roles and roles <= {FULL_STACK, BACKEND, FRONTEND}:
        return FULL_STACK
    return UNKNOWN


def _skill_roles(skills: set[str]) -> set[str]:
    roles = set()
    spring = {"Spring", "Spring Boot", "Spring MVC", "Spring Security"}
    persistence = {"JPA", "Hibernate", "QueryDSL"}
    databases = {"MySQL", "PostgreSQL", "MariaDB", "Oracle", "MongoDB"}
    cloud = {"AWS", "GCP", "Azure"}
    frameworks = {"PyTorch", "TensorFlow"}
    if (skills & spring and skills & ({"Java", "Kotlin", "Redis", "Kafka", "REST API"} | persistence | databases)
            or skills & {"Java", "Kotlin"} and skills & persistence and skills & (databases | {"Redis", "Kafka"})):
        roles.add(BACKEND)
    if (skills & {"Spark", "Airflow"} and skills & ({"SQL", "Kafka"} | cloud)
            or {"Spark", "Airflow"} <= skills):
        roles.add(DATA_ENGINEER)
    if skills & frameworks and skills & {"Python", "Machine Learning", "Deep Learning", "NLP"}:
        roles.add(ML_ENGINEER)
    if skills & {"Tableau", "Power BI", "Looker"} and skills & {"SQL", "Excel"}:
        roles.add(BI_ANALYST)
    if skills & {"Statistics", "A/B Test"} and skills & {"Python", "R", "Pandas", "SQL"}:
        roles.add(DATA_ANALYST)
    if (skills & {"Docker", "Kubernetes"} and skills & {"CI/CD", "Jenkins", "GitHub Actions"}
            and skills & (cloud | {"Linux"})):
        roles.add(DEVOPS)
    # JavaScript/TypeScript alone do not distinguish frontend from backend.
    # Full-stack requires explicit text, never a mixed language/tool collection.
    return roles


def classify_role(posting: dict, skills: list[str]) -> str:
    """Use the strongest available tier; do not break ties with weaker evidence."""
    title = (posting.get("title") or "").casefold()
    description = (posting.get("description") or "").casefold()
    title_role = _resolve(_text_roles(title, _TITLE_RULES))
    if title_role is not None:
        return title_role
    responsibility_role = _resolve(
        _text_roles(title, _RESPONSIBILITY_RULES) | _text_roles(description, _RESPONSIBILITY_RULES)
    )
    if responsibility_role is not None:
        return responsibility_role
    return _resolve(_skill_roles(set(skills))) or UNKNOWN
