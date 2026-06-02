from __future__ import annotations

import re
from collections.abc import Iterable


SKILL_ALIASES = {
    "Python": ["python", "파이썬"],
    "SQL": ["sql", "쿼리"],
    "R": ["r"],
    "Java": ["java"],
    "Pandas": ["pandas"],
    "NumPy": ["numpy"],
    "Statistics": ["statistics", "통계"],
    "A/B Test": ["a/b test", "ab test", "a-b test", "ab테스트", "a/b테스트"],
    "Excel": ["excel", "엑셀"],
    "Tableau": ["tableau", "태블로"],
    "Power BI": ["power bi", "powerbi"],
    "Looker": ["looker"],
    "Plotly": ["plotly"],
    "Spark": ["spark", "스파크"],
    "Airflow": ["airflow"],
    "Kafka": ["kafka"],
    "Docker": ["docker"],
    "Kubernetes": ["kubernetes", "k8s"],
    "AWS": ["aws", "amazon web services"],
    "GCP": ["gcp", "google cloud"],
    "Azure": ["azure"],
    "MySQL": ["mysql"],
    "PostgreSQL": ["postgresql", "postgres"],
    "MongoDB": ["mongodb", "mongo db"],
    "Machine Learning": ["machine learning", "머신러닝", "ml"],
    "Deep Learning": ["deep learning", "딥러닝"],
    "NLP": ["nlp", "자연어"],
    "PyTorch": ["pytorch", "파이토치"],
    "TensorFlow": ["tensorflow", "텐서플로"],
    "Recommender System": ["recommender system", "추천시스템", "추천 시스템"],
    "GA4": ["ga4", "google analytics 4"],
}


def _alias_pattern(alias: str) -> re.Pattern[str]:
    escaped = re.escape(alias.lower())
    return re.compile(rf"(?<![a-z0-9+#.]){escaped}(?![a-z0-9+#.])")


COMPILED_ALIASES = {
    skill: [_alias_pattern(alias) for alias in aliases]
    for skill, aliases in SKILL_ALIASES.items()
}


def extract_skills(*texts: str | None) -> list[str]:
    haystack = " ".join(text or "" for text in texts).lower()
    found = []
    for skill, patterns in COMPILED_ALIASES.items():
        if any(pattern.search(haystack) for pattern in patterns):
            found.append(skill)
    return found


def canonicalize_skills(skills: Iterable[str]) -> list[str]:
    canonical_by_alias = {}
    for canonical, aliases in SKILL_ALIASES.items():
        canonical_by_alias[canonical.lower()] = canonical
        for alias in aliases:
            canonical_by_alias[alias.lower()] = canonical

    result = []
    seen = set()
    for raw_skill in skills:
        value = raw_skill.strip()
        if not value:
            continue
        canonical = canonical_by_alias.get(value.lower(), value)
        if canonical not in seen:
            seen.add(canonical)
            result.append(canonical)
    return result
