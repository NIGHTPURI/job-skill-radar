from __future__ import annotations

from collections import Counter

from .skill_extractor import canonicalize_skills


ROLE_FOUNDATION = {
    "데이터 분석가": ["SQL", "Python", "Statistics", "Pandas", "Tableau"],
    "BI 분석가": ["SQL", "Power BI", "Tableau", "Excel", "Looker"],
    "데이터 엔지니어": ["SQL", "Python", "Spark", "Airflow", "AWS"],
    "ML 엔지니어": ["Python", "Machine Learning", "PyTorch", "Deep Learning", "SQL"],
}


def recommend_skills(
    target_role: str,
    owned_skills: list[str],
    analysis: dict,
    limit: int = 8,
) -> list[dict]:
    owned = set(canonicalize_skills(owned_skills))
    role_skill_counts = analysis.get("role_skill_counts", {})
    target_counts: Counter = role_skill_counts.get(target_role) or analysis.get("skill_counts", Counter())

    foundation = ROLE_FOUNDATION.get(target_role, [])
    candidates = Counter(target_counts)
    for index, skill in enumerate(reversed(foundation), start=1):
        candidates[skill] += index

    recommendations = []
    for skill, frequency in candidates.most_common():
        if skill in owned:
            continue
        reason = "목표 직무 공고에서 자주 등장합니다."
        if skill in foundation:
            reason = "목표 직무의 기초 역량으로 먼저 학습하기 좋습니다."
        recommendations.append(
            {
                "skill": skill,
                "score": frequency,
                "reason": reason,
            }
        )
        if len(recommendations) >= limit:
            break

    return recommendations
