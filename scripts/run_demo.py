from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jobskillradar.analyzer import top_items
from jobskillradar.pipeline import analyze_sample
from jobskillradar.recommender import recommend_skills


def main() -> None:
    analysis = analyze_sample()

    print("Job Skill Radar 샘플 분석")
    print("=" * 32)
    print(f"분석 공고 수: {len(analysis['postings'])}")
    print()

    print("직무 분포")
    for role, count in top_items(analysis["role_counts"]):
        print(f"- {role}: {count}건")
    print()

    print("기술스택 TOP 10")
    for skill, count in top_items(analysis["skill_counts"], limit=10):
        print(f"- {skill}: {count}회")
    print()

    target_role = "데이터 분석가"
    owned_skills = ["SQL"]
    print(f"추천 예시: 목표={target_role}, 보유기술={', '.join(owned_skills)}")
    for item in recommend_skills(target_role, owned_skills, analysis, limit=5):
        print(f"- {item['skill']}: {item['reason']} (점수 {item['score']})")


if __name__ == "__main__":
    main()
