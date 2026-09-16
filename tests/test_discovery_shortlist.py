import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from jobskillradar.discovery_pipeline import discover_work24_jobs, load_discovery_shortlist
from jobskillradar.matcher import compare_profile_to_requirements
from jobskillradar.pipeline import save_profile
from jobskillradar.requirement_extractor import extract_requirements
from jobskillradar.role_classifier import BACKEND, FRONTEND, UNKNOWN
from jobskillradar.shortlist import build_discovery_shortlist
from test_discovery import posting


def item(body='Java required', owned=('Java',), role=BACKEND, pid='one', was_new=True, **profile_fields):
    profile = {'revision': 1, 'owned_skills': list(owned), 'target_roles': [BACKEND],
               'preferred_regions': [], 'required_regions': [], **profile_fields}
    extraction = extract_requirements(None if body is None else {'source': 'work24', 'posting_id': pid, 'job_content': body})
    extraction.update(source='work24', posting_id=pid)
    comparison = compare_profile_to_requirements(profile, extraction, posting_role=role)
    return {'membership': {'source': 'work24', 'posting_id': pid, 'was_new': was_new, 'queries': ['백엔드']},
            'posting': posting(pid, company='Example'), 'comparison': comparison}


def codes(result):
    return [r['code'] for r in result['reasons']]


class DiscoveryShortlistTest(unittest.TestCase):
    def classify(self, **kwargs):
        return build_discovery_shortlist([item(**kwargs)])[0]

    def test_review_first_explains_observed_gaps_not_candidate_quality(self):
        result = self.classify()
        self.assertEqual(result['bucket'], 'review_first')
        self.assertEqual(codes(result), ['found_by_queries', 'new_to_local_database', 'target_role_aligned', 'no_detected_required_profile_gaps'])

    def test_required_independent_gap_is_profile_declaration_only(self):
        result = self.classify(body='Kafka required')
        self.assertEqual(result['bucket'], 'review_with_gaps')
        self.assertIn({'code': 'required_not_listed', 'values': ['Kafka']}, result['reasons'])

    def test_all_of_partial_none_and_full_without_independent_duplication(self):
        for owned, expected in ((('Java',), 'review_with_gaps'), ((), 'review_with_gaps'), (('Java', 'SQL'), 'review_first')):
            with self.subTest(owned=owned):
                result = self.classify(body='Java and SQL required', owned=owned)
                self.assertEqual(result['bucket'], expected)
                self.assertEqual(result['comparison']['required'], [])
                self.assertNotIn('required_not_listed', codes(result))
                self.assertEqual(len(result['comparison']['groups']), 1)

    def test_any_of_either_member_satisfies_single_choice(self):
        for owned, expected in ((('Java',), 'review_first'), (('Kotlin',), 'review_first'), ((), 'review_with_gaps')):
            result = self.classify(body='Java or Kotlin required', owned=owned)
            self.assertEqual(result['bucket'], expected)
            self.assertNotIn('required_not_listed', codes(result))
            if not owned:
                self.assertIn({'code': 'required_any_of_not_represented', 'values': ['Java', 'Kotlin']}, result['reasons'])

    def test_preferred_independent_and_group_gaps_are_not_required_gaps(self):
        for body in ('Java required\nRedis preferred', 'Java required\nAWS or GCP preferred'):
            result = self.classify(body=body)
            self.assertEqual(result['bucket'], 'review_first')
            self.assertTrue(any(code.startswith('preferred_') for code in codes(result)))

    def test_outside_role_and_unknown_role_are_distinct(self):
        self.assertEqual(self.classify(role=FRONTEND)['bucket'], 'outside_current_target')
        self.assertEqual(self.classify(role=UNKNOWN)['bucket'], 'needs_information')

    def test_all_missing_quality_states_are_not_success(self):
        for body, reason in ((None, 'detail_not_fetched'), ('안녕하세요', 'detail_fetched_but_no_requirement_evidence'),
                             ('기술스택: Java', 'requirement_evidence_present_but_unclassified')):
            result = self.classify(body=body)
            self.assertEqual(result['bucket'], 'needs_information')
            self.assertIn(reason, codes(result))

    def test_duty_only_and_uncertain_or_conflicting_evidence_need_review(self):
        for body in ('Java API 개발', 'Java required\n기술스택: Python', 'Java required\nJava preferred',
                     'Java required\nJava is not required'):
            self.assertEqual(self.classify(body=body)['bucket'], 'needs_information')

    def test_hard_region_mismatch_unknown_and_preference_are_separate(self):
        for policy, status, expected in (('required', 'not_satisfied', 'outside_current_target'),
                                         ('required', 'unknown', 'needs_information'),
                                         ('preferred', 'preference_mismatch', 'review_first')):
            value = item()
            value['comparison']['conditions'] = [{'source_field': 'work_region', 'raw_text': '부산',
                                                 'policy': policy, 'status': status}]
            self.assertEqual(build_discovery_shortlist([value])[0]['bucket'], expected)

    def test_hard_unknown_from_real_matcher_contract_is_not_mismatch(self):
        result = self.classify(required_regions=['서울'])
        self.assertEqual(result['bucket'], 'needs_information')
        self.assertIn('hard_condition_unknown', codes(result))
        self.assertNotIn('hard_condition_mismatch', codes(result))

    def test_new_first_stable_ties_input_immutable_no_score_or_probability(self):
        values = [item(pid='z', was_new=False), item(pid='b'), item(pid='a')]
        original = copy.deepcopy(values)
        result = build_discovery_shortlist(values)
        self.assertEqual([r['membership']['posting_id'] for r in result], ['a', 'b', 'z'])
        self.assertEqual(result, build_discovery_shortlist(list(reversed(values))))
        self.assertEqual(values, original)
        def check(value):
            if isinstance(value, dict):
                self.assertFalse(set(value) & {'score', 'probability', 'fit_percentage', 'rank'})
                for nested in value.values(): check(nested)
            elif isinstance(value, list):
                for nested in value: check(nested)
        check(result)
        result[0]['comparison']['required'][0]['evidence'].clear()
        self.assertEqual(values, original)

    def test_inconsistent_identity_or_profile_revision_is_rejected(self):
        first, second = item(), item(pid='two')
        second['comparison']['profile_revision'] = 2
        with self.assertRaises(ValueError):
            build_discovery_shortlist([first, second])
        with self.assertRaises(ValueError):
            build_discovery_shortlist([first, first])
        first['comparison']['posting_id'] = 'wrong'
        with self.assertRaises(ValueError):
            build_discovery_shortlist([first])

    def test_current_profile_recomputes_historic_run_without_network_or_derived_storage(self):
        from test_posting_details import detail
        with tempfile.TemporaryDirectory() as tmp, patch('urllib.request.urlopen', side_effect=AssertionError('No network')):
            path = Path(tmp) / 'radar.sqlite'
            save_profile(db_path=path, target_roles=[BACKEND], owned_skills=[])
            run = discover_work24_jobs('fake', db_path=path, collector=Mock(return_value=[posting('1')]),
                detail_fetcher=lambda **kw: detail(posting_id='1', job_content='Java or Kotlin required',
                    preferred_conditions=None, other_preferred_conditions=None, certificate=None, computer_skill=None,
                    other_information=None, keywords=[]))
            first = load_discovery_shortlist(db_path=path)
            self.assertEqual(first['items'][0]['bucket'], 'review_with_gaps')
            save_profile(db_path=path, target_roles=[BACKEND], owned_skills=['Kotlin'])
            second = load_discovery_shortlist(db_path=path, run_id=run['run_id'])
            self.assertEqual(second['items'][0]['bucket'], 'review_first')
            self.assertEqual((second['run']['profile_revision'], second['profile_revision']), (1, 2))
            self.assertEqual(second['run'], first['run'])


if __name__ == '__main__':
    unittest.main()
