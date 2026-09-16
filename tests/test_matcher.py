import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from jobskillradar.matcher import compare_profile_to_requirements
from jobskillradar.profile import normalize_profile
from jobskillradar.requirement_extractor import extract_requirements
from jobskillradar.role_classifier import BACKEND, DATA_ANALYST, UNKNOWN
from test_requirement_extractor import source_detail


def profile(skills=(), **fields):
    return {**normalize_profile(owned_skills=list(skills), target_roles=[BACKEND], **fields), 'revision': 1}


def compare(text, skills=(), **fields):
    return compare_profile_to_requirements(profile(skills), extract_requirements(source_detail(job_content=text, **fields)))


class MatcherTest(unittest.TestCase):
    def setUp(self):
        for target in ('urllib.request.urlopen', 'sqlite3.connect'):
            blocker = patch(target, side_effect=AssertionError('Pure matcher must not perform I/O'))
            blocker.start()
            self.addCleanup(blocker.stop)

    def test_independent_required_present_and_profile_missing(self):
        result = compare('Java required\nSQL required', ['Java'])
        self.assertEqual({s['skill']: s['status'] for s in result['required']}, {'Java': 'matched', 'SQL': 'profile_missing'})
        self.assertTrue(all(s['evidence'] for s in result['required']))

    def test_preferred_presence_and_absence_are_not_required_gaps(self):
        result = compare('Java preferred\nSQL preferred', ['Java'])
        self.assertEqual({s['skill']: s['status'] for s in result['preferred']},
                         {'Java': 'matched_preferred', 'SQL': 'profile_missing_preferred'})
        self.assertEqual(result['required'], [])

    def test_responsibility_is_context_for_both_present_and_unlisted(self):
        result = compare('Responsibilities\nJava\nSQL', ['Java'])
        self.assertEqual({s['skill']: s['status'] for s in result['responsibilities']},
                         {'Java': 'profile_has', 'SQL': 'profile_not_listed'})
        self.assertEqual(result['required'], [])
        self.assertEqual(result['preferred'], [])

    def test_unspecified_and_negated_evidence_never_become_profile_gaps(self):
        result = compare('Java\nSQL not required\nAWS 경험 없어도 지원 가능')
        self.assertEqual(result['required'], [])
        self.assertEqual(result['preferred'], [])
        self.assertEqual({r['skill'] for r in result['review']}, {'Java', 'SQL', 'AWS'})

    def test_all_of_full_partial_and_absent_without_member_double_count(self):
        for skills, status in ((['Java', 'SQL'], 'satisfied'), (['Java'], 'partially_satisfied'),
                               ([], 'not_satisfied_from_profile')):
            with self.subTest(skills=skills):
                result = compare('Java and SQL required', skills)
                self.assertEqual(result['required'], [])
                self.assertEqual(len(result['groups']), 1)
                group = result['groups'][0]
                self.assertEqual(group['status'], status)
                self.assertEqual(set(group['profile_has']), set(skills))
                self.assertEqual(set(group['profile_not_listed']), {'Java', 'SQL'} - set(skills))

    def test_any_of_either_member_satisfies_one_condition(self):
        for skills, status in ((['Java'], 'satisfied'), (['Kotlin'], 'satisfied'),
                               (['Java', 'Kotlin'], 'satisfied'), ([], 'not_satisfied_from_profile')):
            with self.subTest(skills=skills):
                result = compare('Java or Kotlin required', skills)
                self.assertEqual(result['required'], [])
                self.assertEqual(result['preferred'], [])
                self.assertEqual(result['review'], [])
                self.assertEqual(len(result['groups']), 1)
                self.assertEqual(result['groups'][0]['status'], status)
                self.assertEqual(result['groups'][0]['requirement_type'], 'required')

    def test_preferred_any_of_retains_preference_semantics(self):
        for skills in ([], ['AWS']):
            result = compare('AWS or GCP preferred', skills)
            self.assertEqual(result['required'], [])
            self.assertEqual(result['groups'][0]['requirement_type'], 'preferred')
            self.assertEqual(result['groups'][0]['status'], 'satisfied' if skills else 'not_satisfied_from_profile')

    def test_group_does_not_promote_weaker_independent_evidence(self):
        result = compare('Java and SQL required\nJava preferred', [])
        self.assertEqual(result['required'], [])
        self.assertEqual([s['skill'] for s in result['preferred']], ['Java'])
        self.assertEqual(result['preferred'][0]['status'], 'profile_missing_preferred')
        self.assertEqual(result['groups'][0]['requirement_type'], 'required')
        self.assertEqual(len(result['preferred'][0]['evidence']), 2)

    def test_independent_required_is_not_lost_when_also_in_a_choice(self):
        result = compare('Java or Kotlin required\nJava required', ['Kotlin'])
        self.assertEqual(result['groups'][0]['status'], 'satisfied')
        self.assertEqual([(s['skill'], s['status']) for s in result['required']], [('Java', 'profile_missing')])
        self.assertEqual(len(result['required'][0]['evidence']), 2)

    def test_conflicting_classes_and_negation_keep_all_provenance(self):
        text = 'Java required\nJava preferred\nJava 개발\nJava not required'
        result = compare(text)
        self.assertEqual(result['required'][0]['status'], 'profile_missing')
        self.assertEqual(len(result['required'][0]['evidence']), 4)
        self.assertEqual({r['reason'] for r in result['review']},
                         {'mixed_classifications', 'positive_and_negated_evidence', 'unclassified_evidence'})
        self.assertEqual(result['preferred'], [])

    def test_quality_states_never_create_a_perfect_match_verdict(self):
        cases = [(None, 'detail_not_fetched'), (source_detail(), 'detail_fetched_but_no_requirement_evidence'),
                 (source_detail(job_content='Java'), 'requirement_evidence_present_but_unclassified')]
        for detail, quality in cases:
            with self.subTest(quality=quality):
                result = compare_profile_to_requirements(profile(['Java']), extract_requirements(detail))
                self.assertEqual(result['quality_status'], quality)
                self.assertEqual(result['required'], [])
                self.assertEqual(result['groups'], [])
                self.assertNotIn('overall_status', result)

    def test_unclassified_group_remains_unknown_even_if_owned(self):
        result = compare('Java/Kotlin 중 하나 이상', ['Java'])
        self.assertEqual(result['groups'][0]['status'], 'unknown')
        self.assertEqual(result['review'][0]['reason'], 'unclassified_group')
        self.assertEqual(result['required'], [])

    def test_unmapped_technology_is_review_evidence_not_an_invented_gap(self):
        result = compare('Elixir experience required', ['Elixir'])
        self.assertEqual(result['required'], [])
        self.assertEqual(result['review'][0]['reason'], 'unmapped_evidence')
        self.assertEqual(result['review'][0]['evidence'][0]['evidence_text'], 'Elixir experience required')

    def test_profile_aliases_resolve_without_unknown_or_parent_inference(self):
        raw_profile = {**profile(), 'owned_skills': ['springboot', 'postgres', 'k8s', 'Elixir']}
        extraction = extract_requirements(source_detail(job_content='Spring Boot required\nPostgreSQL preferred\nKubernetes required\nSpring required'))
        result = compare_profile_to_requirements(raw_profile, extraction)
        required = {s['skill']: s['status'] for s in result['required']}
        self.assertEqual(required, {'Spring Boot': 'matched', 'Kubernetes': 'matched', 'Spring': 'profile_missing'})
        self.assertEqual(result['preferred'][0]['status'], 'matched_preferred')

    def test_exact_region_hard_constraints_satisfied_mismatched_or_unknown(self):
        for raw, status in (('서울', 'satisfied'), (' 부산 ', 'not_satisfied'),
                            ('서울 강남구', 'unknown'), ('서울 또는 경기', 'unknown'), ('재택', 'unknown'), (None, 'unknown')):
            with self.subTest(raw=raw):
                extraction = extract_requirements(source_detail(work_region=raw))
                result = compare_profile_to_requirements(profile(required_regions=['서울', '경기']), extraction)
                region = next(c for c in result['conditions'] if c['source_field'] == 'work_region')
                self.assertEqual(region['status'], status)
                self.assertEqual(region['raw_text'], raw)
                self.assertEqual(region['policy'], 'required')

    def test_region_preference_and_constraint_are_separate_results(self):
        extraction = extract_requirements(source_detail(work_region='서울'))
        result = compare_profile_to_requirements(profile(required_regions=['서울'], preferred_regions=['부산']), extraction)
        region = [c for c in result['conditions'] if c['source_field'] == 'work_region']
        self.assertEqual([(c['policy'], c['status']) for c in region],
                         [('required', 'satisfied'), ('preferred', 'preference_mismatch')])
        result = compare_profile_to_requirements(profile(preferred_regions=['서울']), extraction)
        self.assertEqual(result['conditions'][-1]['status'], 'preference_match')

    def test_unconfigured_career_education_employment_are_unknown(self):
        extraction = extract_requirements(source_detail(raw_career_condition='경력무관', education='학사', employment_type='정규직', work_region='서울'))
        result = compare_profile_to_requirements(profile(), extraction)
        self.assertEqual(len(result['conditions']), 4)
        self.assertTrue(all(c['status'] == 'unknown' and c['policy'] == 'not_configured' for c in result['conditions']))
        self.assertEqual(result['conditions'][0]['raw_text'], '경력무관')

    def test_role_alignment_does_not_change_skill_comparison(self):
        extraction = extract_requirements(source_detail(job_content='SQL required'))
        results = []
        for role, state in ((BACKEND, 'target_role'), (DATA_ANALYST, 'outside_target_roles'), (UNKNOWN, 'unknown'), (None, 'unknown')):
            result = compare_profile_to_requirements(profile(), extraction, posting_role=role)
            self.assertEqual(result['role_alignment'], state)
            results.append(result['required'])
        self.assertTrue(all(r == results[0] for r in results))

    def test_determinism_input_independence_and_no_score_contract(self):
        extraction = extract_requirements(source_detail(job_content='Java or Kotlin required\nSQL preferred\nPython'))
        saved = profile(['Java'])
        before = copy.deepcopy((saved, extraction))
        first = compare_profile_to_requirements(saved, extraction)
        second = compare_profile_to_requirements(saved, extraction)
        self.assertEqual(first, second)
        self.assertEqual((saved, extraction), before)
        forbidden = {'score', 'fit', 'fit_percentage', 'probability', 'ranking', 'overall_status'}
        def check(value):
            if isinstance(value, dict):
                self.assertFalse(forbidden & value.keys())
                for child in value.values():
                    check(child)
            elif isinstance(value, list):
                for child in value:
                    check(child)
        check(first)
        first['groups'][0]['evidence']['evidence_text'] = 'modified'
        self.assertEqual(compare_profile_to_requirements(saved, extraction), second)
        self.assertEqual((saved, extraction), before)

    def test_missing_profile_or_unreviewed_extractor_contract_fails_visibly(self):
        extraction = extract_requirements(source_detail(job_content='Java required'))
        with self.assertRaises(ValueError):
            compare_profile_to_requirements(None, extraction)
        with self.assertRaises(ValueError):
            compare_profile_to_requirements(profile(), {**extraction, 'extractor_version': 1})


if __name__ == '__main__':
    unittest.main()
