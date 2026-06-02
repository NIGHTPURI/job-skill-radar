from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jobskillradar.pipeline import analyze_sample
from jobskillradar.recommender import recommend_skills
from jobskillradar.skill_extractor import canonicalize_skills, extract_skills


class CoreTest(unittest.TestCase):
    def test_extract_skills(self) -> None:
        skills = extract_skills("SQL과 파이썬", "Tableau 대시보드와 A/B Test")
        self.assertIn("SQL", skills)
        self.assertIn("Python", skills)
        self.assertIn("Tableau", skills)
        self.assertIn("A/B Test", skills)

    def test_canonicalize_skills(self) -> None:
        self.assertEqual(canonicalize_skills(["sql", "파이썬", "Python"]), ["SQL", "Python"])

    def test_recommend_skills(self) -> None:
        analysis = analyze_sample()
        recommendations = recommend_skills("데이터 분석가", ["SQL"], analysis)
        recommended_skills = [item["skill"] for item in recommendations]
        self.assertNotIn("SQL", recommended_skills)
        self.assertIn("Python", recommended_skills)


if __name__ == "__main__":
    unittest.main()
