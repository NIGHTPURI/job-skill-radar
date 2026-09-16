"""Role-scoped learning priorities from posting mentions and small foundations.

Foundations are optional learning suggestions, not universal job requirements.
Market counts always outrank foundations; no global fallback or synthetic score.
"""
from __future__ import annotations

from .models import AnalysisResult, SkillRecommendation
from .role_classifier import (
    BACKEND, BI_ANALYST, DATA_ANALYST, DATA_ENGINEER, DEVOPS,
    FRONTEND, FULL_STACK, ML_ENGINEER,
)
from .skill_extractor import canonicalize_skills


# Membership only: declaration order carries no weight or prerequisite ordering.
# Avoid prescribing a vendor, backend language, or framework without evidence.
ROLE_FOUNDATION = {
    BACKEND: ("Git", "REST API", "SQL"),
    FRONTEND: ("Git", "JavaScript"),
    FULL_STACK: ("Git", "JavaScript", "REST API", "SQL"),
    DATA_ANALYST: ("Python", "SQL", "Statistics"),
    BI_ANALYST: ("Excel", "SQL", "Statistics"),
    DATA_ENGINEER: ("Git", "Python", "SQL"),
    ML_ENGINEER: ("Machine Learning", "Python", "Statistics"),
    DEVOPS: ("CI/CD", "Git", "Linux"),
}


def recommend_skills(
    target_role: str,
    owned_skills: list[str],
    analysis: AnalysisResult,
    limit: int = 8,
) -> list[SkillRecommendation]:
    """Rank unowned skills by count, foundation membership, then canonical name.

    Consume analyzer aggregates without I/O or mutation. Legacy partial dicts
    remain accepted: missing role counts mean an unknown denominator (None),
    not zero postings. Missing skill counts contribute no market evidence.
    Unknown/unsupported roles and non-positive limits return an empty list.
    """
    if limit <= 0 or target_role not in ROLE_FOUNDATION:
        return []

    owned = set(canonicalize_skills(owned_skills))
    foundation = set(ROLE_FOUNDATION[target_role])
    counts = analysis.get("role_skill_counts", {}).get(target_role, {})
    role_posting_count = analysis["role_counts"].get(target_role, 0) if "role_counts" in analysis else None
    candidates = (foundation | {skill for skill, count in counts.items() if count > 0}) - owned
    ordered = sorted(candidates, key=lambda skill: (
        -counts.get(skill, 0), skill not in foundation, skill.casefold(), skill,
    ))

    recommendations: list[SkillRecommendation] = []
    for priority, skill in enumerate(ordered[:limit], start=1):
        count = counts.get(skill, 0)
        is_foundation = skill in foundation
        if count > 0:
            if role_posting_count is None:
                reason = f"현재 분석한 {target_role} 공고 {count}건에서 언급되었습니다. 전체 역할 공고 수는 제공되지 않았습니다."
            else:
                reason = f"현재 분석한 {target_role} 공고 {role_posting_count}건 중 {count}건에서 언급되었습니다."
            if is_foundation:
                reason += " 역할 기초 학습 후보이기도 합니다."
        elif role_posting_count == 0:
            reason = f"현재 분석한 {target_role} 공고가 없어 기초 학습 후보로만 추천합니다."
        elif role_posting_count is None:
            reason = f"{target_role} 공고 수가 제공되지 않았고 이 기술의 역할별 언급 근거가 없어 기초 학습 후보로만 추천합니다."
        else:
            reason = f"현재 분석한 {target_role} 공고 {role_posting_count}건에서 이 기술의 언급은 추출되지 않아 기초 학습 후보로만 추천합니다."
        recommendations.append({
            "skill": skill,
            "priority": priority,
            "market_count": count,
            "role_posting_count": role_posting_count,
            "is_foundation": is_foundation,
            "evidence_source": "role_market" if count > 0 else "foundation_only",
            "reason": reason,
        })

    return recommendations
