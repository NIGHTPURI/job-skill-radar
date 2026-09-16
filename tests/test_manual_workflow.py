import copy
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from jobskillradar import pipeline, storage


class ManualWorkflowTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / 'manual.sqlite'
        blocker = patch('urllib.request.urlopen', side_effect=AssertionError('Unexpected HTTP'))
        blocker.start()
        self.addCleanup(blocker.stop)

    def create(self, **changes):
        return pipeline.create_manual_posting(db_path=self.path, **{
            'company': 'Example', 'title': 'Backend Engineer', 'body': 'Java or Kotlin required', **changes})

    def review(self, identity):
        return pipeline.load_posting_review('manual', identity, db_path=self.path)

    def dump(self):
        with closing(storage.connect(self.path)) as conn:
            return list(conn.iterdump())

    def test_minimal_create_reloads_stable_unique_identity_and_requirements(self):
        first, second = self.create(), self.create()
        self.assertNotEqual(first, second)
        self.assertEqual(str(UUID(first)), first)
        review = self.review(first)
        self.assertEqual(review, self.review(first))
        self.assertEqual((review['posting']['source'], review['posting']['posting_id']), ('manual', first))
        self.assertEqual(review['detail']['source'], 'manual')
        self.assertEqual(review['requirements']['groups'][0]['relation'], 'any_of')
        self.assertTrue(all(s['requirement_type'] == 'unspecified' for s in review['requirements']['skills']))
        self.assertEqual(len(pipeline.list_saved_postings(db_path=self.path)), 2)

    def test_raw_body_and_optional_metadata_are_preserved_without_fabrication(self):
        body = '  [자격요건]\r\n\r\n  Java 필수\n\tSQL\n  '
        identity = self.create(body=body, url='https://example.org/jobs/1', region='서울 강남구', career='경력무관',
                               education='학사 또는 동등 경험', closing_at='채용 시 마감', captured_at='2026-09-17T00:00:00Z')
        review = self.review(identity)
        self.assertEqual(review['detail']['job_content'], body)
        self.assertEqual(review['posting']['description'], '')
        self.assertEqual(review['posting']['career'], '무관')
        self.assertEqual(review['detail']['raw_career_condition'], '경력무관')
        self.assertEqual(review['detail']['work_region'], '서울 강남구')
        self.assertEqual(review['detail']['education'], '학사 또는 동등 경험')
        self.assertEqual(review['detail']['closing_at'], '채용 시 마감')
        self.assertEqual(review['detail']['fetched_at'], '2026-09-17T00:00:00Z')
        self.assertIsNone(review['detail']['employment_type'])
        self.assertEqual(review['detail']['keywords'], [])

    def test_blank_required_fields_rejected_before_persistence(self):
        for field in ('company', 'title', 'body'):
            for blank in ('', ' \n\t', None):
                with self.subTest(field=field, blank=blank), self.assertRaises(ValueError):
                    self.create(**{field: blank})
        self.assertFalse(self.path.exists())

    def test_invalid_url_or_optional_types_rejected(self):
        for values in ({'url': 'javascript:alert(1)'}, {'url': '/relative'}, {'region': []}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.create(**values)

    def test_edit_preserves_identity_created_at_and_reprocesses_latest_body(self):
        identity = self.create()
        with closing(storage.connect(self.path)) as conn:
            created = conn.execute('SELECT created_at FROM job_postings').fetchone()
        pipeline.update_manual_posting('manual', identity, db_path=self.path, company='Changed', title='Python Developer',
                                       body='Python required', url='https://example.org/new', region='부산', career='신입',
                                       education='무관', closing_at='2026-10-01', captured_at='2026-09-18T00:00:00Z')
        review = self.review(identity)
        self.assertEqual((review['posting']['source'], review['posting']['posting_id']), ('manual', identity))
        self.assertEqual(review['posting']['company'], 'Changed')
        self.assertEqual(review['posting']['url'], 'https://example.org/new')
        self.assertEqual(review['detail']['job_content'], 'Python required')
        self.assertEqual(review['detail']['work_region'], '부산')
        self.assertEqual([s['skill'] for s in review['requirements']['skills']], ['Python'])
        self.assertEqual(review['requirements']['groups'], [])
        with closing(storage.connect(self.path)) as conn:
            self.assertEqual(conn.execute('SELECT created_at FROM job_postings').fetchone(), created)
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 4)

    def test_work24_edit_rejected_even_with_same_posting_id(self):
        identity = self.create(id_factory=lambda: 'shared')
        storage.save_postings_to_db(self.path, [{'source': 'work24', 'posting_id': identity, 'title': 'Original'}])
        before = self.dump()
        with self.assertRaisesRegex(ValueError, 'Only manual'):
            pipeline.update_manual_posting('work24', identity, db_path=self.path, company='X', title='X', body='X')
        self.assertEqual(self.dump(), before)
        pipeline.update_manual_posting('manual', identity, db_path=self.path, company='X', title='X', body='SQL required')
        self.assertEqual(pipeline.load_posting_review('work24', identity, db_path=self.path)['posting']['title'], 'Original')

    def test_create_collision_does_not_overwrite_existing_data(self):
        self.create(id_factory=lambda: 'fixed')
        before = self.dump()
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.create(id_factory=lambda: 'fixed', body='Python')
        self.assertEqual(self.dump(), before)

    def test_missing_edit_does_not_create_a_posting(self):
        with self.assertRaisesRegex(ValueError, 'does not exist'):
            pipeline.update_manual_posting('manual', 'missing', db_path=self.path, company='X', title='X', body='SQL')
        self.assertEqual(pipeline.list_saved_postings(db_path=self.path), [])

    def test_detail_write_failure_rolls_back_create_and_edit(self):
        storage.save_postings_to_db(self.path, [])
        for edit in (False, True):
            if edit:
                identity = self.create()
            before = self.dump()
            with patch.object(storage, 'save_posting_details', side_effect=sqlite3.IntegrityError('injected')):
                with self.assertRaises(sqlite3.IntegrityError):
                    if edit:
                        pipeline.update_manual_posting('manual', identity, db_path=self.path, company='X', title='X', body='SQL')
                    else:
                        self.create()
            self.assertEqual(self.dump(), before)

    def test_invalid_capture_timestamp_rolls_back_parent_and_skills(self):
        with self.assertRaises(ValueError):
            self.create(captured_at='invalid')
        self.assertEqual(pipeline.list_saved_postings(db_path=self.path), [])
        with closing(storage.connect(self.path)) as conn:
            self.assertEqual(conn.execute('SELECT * FROM posting_skills').fetchall(), [])

    def test_storage_boundary_enforces_manual_ownership_and_same_identity(self):
        identity = self.create()
        review = self.review(identity)
        before = self.dump()
        for source in ('work24', 'other'):
            posting = {**review['posting'], 'source': source}
            with self.assertRaises(ValueError):
                storage.save_manual_bundle_to_db(self.path, posting, review['detail'], create=False)
        self.assertEqual(self.dump(), before)

    def test_manual_posts_never_enter_implicit_or_dashboard_market_analysis(self):
        self.create(body='Python required', title='Python Developer')
        self.assertIsNone(pipeline.load_db_analysis(db_path=self.path))
        self.assertEqual(pipeline.load_market_analysis('DB 우선', db_path=self.path)[1], '샘플')
        storage.save_postings_to_db(self.path, [{'source': 'work24', 'posting_id': 'w', 'title': 'Java Developer'},
                                               {'source': 'sample', 'posting_id': 's', 'title': 'SQL Developer'}])
        analysis, label = pipeline.load_market_analysis('DB 우선', db_path=self.path)
        self.assertEqual(label, '고용24')
        self.assertEqual(analysis['skill_counts'], {'Java': 1})
        self.assertEqual({p['source'] for p in analysis['postings']}, {'work24'})
        self.assertNotIn('Python', pipeline.load_db_analysis(db_path=self.path)['skill_counts'])

    def test_review_preserves_quality_and_groups_for_manual_and_work24(self):
        identity = self.create(body='Welcome to our team')
        self.assertEqual(self.review(identity)['requirements']['quality_status'], 'detail_fetched_but_no_requirement_evidence')
        pipeline.update_manual_posting('manual', identity, db_path=self.path, company='X', title='X', body='Java')
        self.assertEqual(self.review(identity)['requirements']['quality_status'], 'requirement_evidence_present_but_unclassified')
        storage.save_postings_to_db(self.path, [{'source': 'work24', 'posting_id': 'w'}])
        self.assertEqual(pipeline.load_posting_review('work24', 'w', db_path=self.path)['requirements']['quality_status'], 'detail_not_fetched')

    def test_review_closes_snapshot_connection_before_pure_extraction(self):
        identity = self.create()
        conn = storage.connect(self.path)
        original = pipeline.extract_requirements
        def check(detail):
            with self.assertRaises(sqlite3.ProgrammingError):
                conn.execute('SELECT 1')
            return original(detail)
        with patch.object(storage, 'connect', return_value=conn), patch.object(pipeline, 'extract_requirements', side_effect=check):
            self.review(identity)


if __name__ == '__main__':
    unittest.main()
