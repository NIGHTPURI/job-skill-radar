import copy
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from jobskillradar import pipeline, storage
from jobskillradar.profile import normalize_profile
from jobskillradar.role_classifier import BACKEND, DATA_ANALYST


class ProfileTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / 'profile.sqlite'
        blocker = patch('urllib.request.urlopen', side_effect=AssertionError('Unexpected HTTP'))
        blocker.start()
        self.addCleanup(blocker.stop)

    def save(self, **changes):
        return pipeline.save_profile(db_path=self.path, **{
            'owned_skills': ['springboot', 'postgres', 'k8s', 'Elixir'],
            'target_roles': [BACKEND, DATA_ANALYST], **changes})

    def test_first_save_reload_and_multiple_targets(self):
        self.assertIsNone(pipeline.load_profile(db_path=self.path))
        profile = self.save()
        self.assertEqual(profile['revision'], 1)
        self.assertEqual(set(profile['owned_skills']), {'Spring Boot', 'PostgreSQL', 'Kubernetes', 'Elixir'})
        self.assertEqual(set(profile['target_roles']), {BACKEND, DATA_ANALYST})
        self.assertEqual(profile, pipeline.load_profile(db_path=self.path))
        self.assertEqual((profile['preferred_regions'], profile['required_regions']), ([], []))

    def test_revision_ignores_alias_order_duplicates_and_padding(self):
        first = self.save()
        again = self.save(owned_skills=['Elixir', 'Kubernetes', ' Spring Boot ', 'PostgreSQL', 'springboot'],
                          target_roles=[DATA_ANALYST, BACKEND, BACKEND])
        self.assertEqual(first, again)
        changed = self.save(owned_skills=['Python'])
        self.assertEqual(changed['revision'], 2)
        self.assertEqual(changed['owned_skills'], ['Python'])
        self.assertEqual(pipeline.load_profile(db_path=self.path), changed)

    def test_preferences_and_constraints_are_separate_and_revisioned(self):
        first = self.save(preferred_regions=['서울', '경기'], required_regions=['서울'])
        self.assertEqual(set(first['preferred_regions']), {'서울', '경기'})
        self.assertEqual(first['required_regions'], ['서울'])
        second = self.save(preferred_regions=['서울'], required_regions=['서울', '경기'])
        self.assertEqual(second['revision'], 2)
        self.assertEqual(set(second['required_regions']), {'서울', '경기'})
        cleared = self.save()
        self.assertEqual(cleared['revision'], 3)
        self.assertEqual(cleared['required_regions'], [])

    def test_unknown_skills_preserved_without_inference_and_empty_skills_allowed(self):
        result = self.save(owned_skills=['Elixir', 'Elixir', 'Spring Boot'])
        self.assertEqual(result['owned_skills'], ['Elixir', 'Spring Boot'])
        self.assertNotIn('Spring', result['owned_skills'])
        self.assertEqual(self.save(owned_skills=[])['owned_skills'], [])

    def test_invalid_fields_do_not_replace_valid_profile(self):
        self.save()
        before = pipeline.load_profile(db_path=self.path)
        for fields in ({'owned_skills': 'SQL'}, {'owned_skills': [None]}, {'target_roles': []},
                       {'target_roles': ['unknown']}, {'preferred_regions': ['Anywhere']},
                       {'required_regions': '서울'}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                self.save(**fields)
            self.assertEqual(pipeline.load_profile(db_path=self.path), before)

    def test_normalization_is_pure_and_does_not_mutate_input(self):
        values = {'owned_skills': ['k8s', 'SQL', 'SQL'], 'target_roles': [BACKEND], 'preferred_regions': ['서울']}
        before = copy.deepcopy(values)
        first = normalize_profile(**values)
        self.assertEqual(first, normalize_profile(**values))
        self.assertEqual(values, before)
        first['owned_skills'].clear()
        self.assertTrue(normalize_profile(**values)['owned_skills'])

    def test_failed_update_rolls_back_revision_and_values(self):
        old = self.save()
        with closing(storage.connect(self.path)) as conn:
            conn.execute("CREATE TRIGGER fail_profile BEFORE UPDATE ON user_profile BEGIN SELECT RAISE(ABORT, 'injected'); END")
            conn.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.save(owned_skills=['Python'])
        self.assertEqual(pipeline.load_profile(db_path=self.path), old)

    def test_first_write_failure_leaves_no_partial_profile(self):
        pipeline.load_profile(db_path=self.path)
        with closing(storage.connect(self.path)) as conn:
            conn.execute("CREATE TRIGGER fail_profile BEFORE INSERT ON user_profile BEGIN SELECT RAISE(ABORT, 'injected'); END")
            conn.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.save()
        self.assertIsNone(pipeline.load_profile(db_path=self.path))

    def test_profile_does_not_change_manual_work24_or_market_data(self):
        identity = pipeline.create_manual_posting(db_path=self.path, company='Example', title='Backend', body='Java required')
        storage.save_postings_to_db(self.path, [{'source': 'work24', 'posting_id': identity, 'title': 'SQL'}])
        before = pipeline.load_posting_review('manual', identity, db_path=self.path)
        market = pipeline.load_market_analysis('DB 우선', db_path=self.path)
        self.save()
        self.assertEqual(pipeline.load_posting_review('manual', identity, db_path=self.path), before)
        self.assertEqual(pipeline.load_market_analysis('DB 우선', db_path=self.path), market)

    def test_singleton_constraint_blocks_second_profile(self):
        self.save()
        with closing(storage.connect(self.path)) as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO user_profile SELECT 2, revision, owned_skills, target_roles, preferred_regions, required_regions FROM user_profile")

    def test_corrupt_json_fails_visibly(self):
        self.save()
        with closing(storage.connect(self.path)) as conn:
            conn.execute("UPDATE user_profile SET owned_skills='invalid JSON'")
            conn.commit()
        with self.assertRaises(ValueError):
            pipeline.load_profile(db_path=self.path)


if __name__ == '__main__':
    unittest.main()
