"""Pure explainable review organization. Buckets are not qualification verdicts."""
from __future__ import annotations

from copy import deepcopy

from .models import DiscoveryReviewItem

BUCKET_ORDER = ('review_first', 'review_with_gaps', 'needs_information', 'outside_current_target')


def build_discovery_shortlist(items: list[dict]) -> list[DiscoveryReviewItem]:
    """Consume current comparisons, retaining historic discovery provenance.

    Reliable exclusion first, then uncertainty, then explicit required gaps.
    Any review evidence conservatively prevents review_first. Duty-only evidence
    cannot establish sufficient qualification coverage. Preferred gaps never
    become required gaps. Stable presentation order is independent of input order.
    """
    results = []
    identities = set()
    revisions = set()
    for item in items:
        member, posting, comparison = item['membership'], item['posting'], item['comparison']
        identity = member['source'], member['posting_id']
        if identity in identities or any((obj['source'], obj['posting_id']) != identity for obj in (posting, comparison)):
            raise ValueError('Shortlist identities must be unique and aligned')
        identities.add(identity)
        revisions.add(comparison['profile_revision'])
        reasons = []
        def reason(code, values=()):
            value = {'code': code, 'values': list(values)}
            if value not in reasons:
                reasons.append(value)
        reason('found_by_queries', member['queries'])
        reason('new_to_local_database' if member['was_new'] else 'known_to_local_database')
        role = comparison['role_alignment']
        reason({'target_role': 'target_role_aligned', 'outside_target_roles': 'outside_target_roles',
                'unknown': 'role_unknown'}[role], [comparison['posting_role']] if comparison['posting_role'] else [])
        hard_mismatch = False
        hard_unknown = False
        for condition in comparison['conditions']:
            if condition['policy'] == 'required':
                if condition['status'] == 'not_satisfied':
                    hard_mismatch = True
                    reason('hard_condition_mismatch', [condition['source_field'], condition['raw_text'] or ''])
                elif condition['status'] == 'unknown':
                    hard_unknown = True
                    reason('hard_condition_unknown', [condition['source_field']])
            elif condition['status'] == 'preference_mismatch':
                reason('condition_preference_mismatch', [condition['source_field'], condition['raw_text'] or ''])
        missing = [r['skill'] for r in comparison['required'] if r['status'] == 'profile_missing']
        if missing:
            reason('required_not_listed', missing)
        group_gaps = []
        for group in comparison['groups']:
            if group['requirement_type'] == 'required' and group['status'] in ('partially_satisfied', 'not_satisfied_from_profile'):
                group_gaps.append(group)
                reason('required_' + group['relation'] + '_not_represented', group['skills'])
            elif group['requirement_type'] == 'preferred' and group['status'] in ('partially_satisfied', 'not_satisfied_from_profile'):
                reason('preferred_' + group['relation'] + '_not_represented', group['skills'])
        preferred_missing = [r['skill'] for r in comparison['preferred'] if r['status'] == 'profile_missing_preferred']
        if preferred_missing:
            reason('preferred_not_listed', preferred_missing)
        quality = comparison['quality_status']
        if quality != 'requirements_extracted':
            reason(quality)
        if comparison['review']:
            reason('evidence_needs_review', sorted({r['reason'] for r in comparison['review']}))
        qualification = bool(comparison['required'] or comparison['preferred'] or any(
            g['requirement_type'] in ('required', 'preferred') for g in comparison['groups']))
        if quality == 'requirements_extracted' and not qualification:
            reason('no_classified_qualification_evidence')
        if role == 'outside_target_roles' or hard_mismatch:
            bucket = 'outside_current_target'
        elif role == 'unknown' or quality != 'requirements_extracted' or comparison['review'] or hard_unknown or not qualification:
            bucket = 'needs_information'
        elif missing or group_gaps:
            bucket = 'review_with_gaps'
        else:
            bucket = 'review_first'
            reason('no_detected_required_profile_gaps')
        results.append({**item, 'bucket': bucket, 'reasons': reasons})
    if len(revisions) > 1:
        raise ValueError('Shortlist comparisons must use one current profile revision')
    results.sort(key=lambda item: (
        BUCKET_ORDER.index(item['bucket']), not item['membership']['was_new'],
        (item['posting'].get('company') or '').casefold(), (item['posting'].get('title') or '').casefold(),
        item['membership']['source'], item['membership']['posting_id']))
    return deepcopy(results)
