import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jobskillradar.analyzer import analyze_postings
from jobskillradar.models import JobPosting, POSTING_FIELDS
from jobskillradar.normalizer import clean_posting
from jobskillradar.work24_client import _parse_list_response


class PostingContractTest(unittest.TestCase):
    def test_base_field_order_matches_existing_public_contract(self):
        self.assertEqual(POSTING_FIELDS, (
            "source", "posting_id", "company", "title", "description", "region", "career",
            "education", "salary_type", "salary", "job_code", "registered_at", "closing_at", "url",
        ))

    def test_partial_dictionary_and_explicit_none_stay_distinct(self):
        posting = JobPosting(title="SQL", career=None)
        self.assertIs(type(posting), dict)
        self.assertNotIn("region", posting)
        result = analyze_postings([posting])
        self.assertEqual(result["career_counts"], {None: 1})
        self.assertEqual(result["region_counts"], {"미상": 1})

    def test_collection_and_normalization_share_base_fields(self):
        posting = _parse_list_response("<root><wanted><wantedAuthNo>1</wantedAuthNo></wanted></root>")[0]
        self.assertEqual(tuple(posting), POSTING_FIELDS)
        self.assertEqual(tuple(clean_posting(posting)), POSTING_FIELDS)

    def test_generated_fields_do_not_leak_into_normalized_contract(self):
        raw = {"posting_id": "1", "title": "SQL", "skills": ["Java"], "role": "old", "custom": "keep"}
        enriched = analyze_postings([raw])["postings"][0]
        self.assertEqual(enriched["skills"], ["SQL"])
        self.assertEqual(enriched["custom"], "keep")
        self.assertEqual(tuple(clean_posting(enriched)), POSTING_FIELDS)


if __name__ == "__main__":
    unittest.main()
