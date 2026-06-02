from __future__ import annotations

from collections import Counter, defaultdict

from .skill_extractor import extract_skills


ROLE_LABELS = [
    "데이터 분석가",
    "데이터 엔지니어",
    "ML 엔지니어",
    "BI 분석가",
]


def classify_role(posting: dict, skills: list[str]) -> str:
    title = posting.get("title", "").lower()
    text = f"{title} {posting.get('description', '')}".lower()
    skill_set = set(skills)

    if any(token in title for token in ["bi", "kpi"]):
        return "BI 분석가"

    if any(token in title for token in ["데이터 분석", "분석가", "분석 담당"]):
        return "데이터 분석가"

    if any(token in text for token in ["엔지니어", "파이프라인", "etl", "플랫폼"]) or skill_set & {
        "Spark",
        "Airflow",
        "Kafka",
        "Docker",
        "Kubernetes",
    }:
        if skill_set & {"Machine Learning", "Deep Learning", "NLP", "PyTorch", "TensorFlow"}:
            return "ML 엔지니어"
        return "데이터 엔지니어"

    if any(token in text for token in ["머신러닝", "ml", "ai", "딥러닝", "nlp"]) or skill_set & {
        "Machine Learning",
        "Deep Learning",
        "NLP",
        "PyTorch",
        "TensorFlow",
    }:
        return "ML 엔지니어"

    if any(token in text for token in ["bi", "대시보드", "dashboard", "kpi"]) or skill_set & {
        "Tableau",
        "Power BI",
        "Looker",
    }:
        return "BI 분석가"

    return "데이터 분석가"


def enrich_posting(posting: dict) -> dict:
    skills = extract_skills(posting.get("title"), posting.get("description"))
    role = classify_role(posting, skills)
    return {
        **posting,
        "skills": skills,
        "role": role,
    }


def analyze_postings(postings: list[dict]) -> dict:
    enriched = [enrich_posting(posting) for posting in postings]

    skill_counts = Counter()
    role_counts = Counter()
    career_counts = Counter()
    region_counts = Counter()
    role_skill_counts: dict[str, Counter] = defaultdict(Counter)

    for posting in enriched:
        role = posting["role"]
        role_counts[role] += 1
        career_counts[posting.get("career", "미상")] += 1
        region_counts[posting.get("region", "미상")] += 1
        for skill in posting["skills"]:
            skill_counts[skill] += 1
            role_skill_counts[role][skill] += 1

    return {
        "postings": enriched,
        "skill_counts": skill_counts,
        "role_counts": role_counts,
        "career_counts": career_counts,
        "region_counts": region_counts,
        "role_skill_counts": dict(role_skill_counts),
    }


def top_items(counter: Counter, limit: int = 10) -> list[tuple[str, int]]:
    return counter.most_common(limit)
