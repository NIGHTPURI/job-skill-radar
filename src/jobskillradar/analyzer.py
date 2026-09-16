from __future__ import annotations

from collections import Counter, defaultdict

from .models import AnalysisResult, JobPosting
from .skill_extractor import extract_skills
from .role_classifier import ROLE_LABELS, classify_role


def enrich_posting(posting: dict) -> JobPosting:
    skills = extract_skills(posting.get("title"), posting.get("description"))
    role = classify_role(posting, skills)
    return {
        **posting,
        "skills": skills,
        "role": role,
    }


def analyze_postings(postings: list[dict]) -> AnalysisResult:
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
