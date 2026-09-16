import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jobskillradar.normalizer import clean_posting, clean_postings, normalize_career, normalize_region


class NormalizerTest(unittest.TestCase):
    def test_clean_posting_field_contract_and_no_mutation(self):
        raw = {"posting_id": 123, "title": " SQL ", "company": None, "region": "서울 강남구",
               "career": "경력 3년", "extra": "discard"}
        original = copy.deepcopy(raw)
        result = clean_posting(raw)
        self.assertEqual(result, {
            "source": "", "posting_id": "123", "company": "", "title": "SQL", "description": "",
            "region": "서울", "career": "경력", "education": "", "salary_type": "", "salary": "",
            "job_code": "", "registered_at": "", "closing_at": "", "url": "",
        })
        self.assertEqual(raw, original)

    def test_empty_postings_and_missing_ids_are_discarded(self):
        self.assertEqual(clean_postings([]), [])
        self.assertEqual(clean_postings([{}, {"posting_id": None}, {"posting_id": "  "}]), [])

    def test_duplicate_ids_keep_first_after_stripping(self):
        result = clean_postings([{"posting_id": " 1 ", "title": "first"},
                                 {"posting_id": "1", "title": "second"}, {"posting_id": "2"}])
        self.assertEqual([(p["posting_id"], p["title"]) for p in result], [("1", "first"), ("2", "")])

    def test_deduplication_preserves_distinct_sources(self):
        result = clean_postings([{"source": "a", "posting_id": "1"}, {"source": "b", "posting_id": "1"}])
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["source"], "a")

    def test_region_aliases_unknown_and_empty(self):
        for raw, expected in [("서울특별시 강남구", "서울"), ("판교", "경기"),
                              ("경기도 광주시", "경기"), ("창원", "경남"),
                              ("overseas city", "overseas"), (None, "미상"), ("  ", "미상")]:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_region(raw), expected)

    def test_career_categories_and_current_mixed_precedence(self):
        for raw, expected in [(None, "미상"), ("", "미상"), ("신입", "신입"),
                              ("경력 3년", "경력"), ("무관", "무관"), ("관계없음", "무관"),
                              ("intern", "기타"), ("신입/경력", "신입"), ("경력무관", "경력")]:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_career(raw), expected)

    @unittest.expectedFailure
    def test_kd08_no_experience_requirement_should_be_unrestricted(self):
        """KD-08 / Phase 4C: substring priority reverses the meaning of 경력무관."""
        self.assertEqual(normalize_career("경력무관"), "무관")

    def test_dates_and_salary_are_currently_only_trimmed(self):
        result = clean_posting({"registered_at": " 26/9/1 ", "salary": " 협의 "})
        self.assertEqual(result["registered_at"], "26/9/1")
        self.assertEqual(result["salary"], "협의")


if __name__ == "__main__":
    unittest.main()
