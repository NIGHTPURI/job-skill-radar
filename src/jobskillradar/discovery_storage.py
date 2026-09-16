"""Short database operations used by discovery; never retain connections for HTTP."""
from __future__ import annotations

from contextlib import closing
from pathlib import Path

from . import storage


def load_discovery_state(path: Path) -> tuple[set[str], set[str]]:
    with closing(storage.connect(path)) as conn:
        storage.ensure_schema(conn)
        with conn:
            conn.execute("BEGIN")
            known = {row[0] for row in conn.execute("SELECT posting_id FROM job_postings WHERE source='work24'")}
            detailed = {row[0] for row in conn.execute("SELECT posting_id FROM posting_details WHERE source='work24'")}
            return known, detailed


def save_discovery_batch(path: Path, result: dict, postings: list[dict], details: list[dict]) -> dict:
    """Determine newness immediately before insertion under the same write lock."""
    if {(p['source'], p['posting_id']) for p in postings} != {(m['source'], m['posting_id']) for m in result['postings']}:
        raise ValueError('Posting batch must match discovery membership')
    detail_ids = {(d['source'], d['posting_id']) for d in details}
    if (len(details) != len(detail_ids) or not detail_ids <= {(m['source'], m['posting_id']) for m in result['postings']}
            or len(details) != result['details_saved']):
        raise ValueError('Detail batch must match discovery count')
    with closing(storage.connect(path)) as conn:
        storage.ensure_schema(conn)
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            for member in result["postings"]:
                member["was_new"] = conn.execute(
                    "SELECT 1 FROM job_postings WHERE source=? AND posting_id=?",
                    (member["source"], member["posting_id"])).fetchone() is None
            storage.save_postings(conn, postings)
            storage.save_posting_details(conn, details)
            result["new_postings"] = sum(member["was_new"] for member in result["postings"])
            _insert_run(conn, result)
    return result


RUN_COLUMNS = ('run_id', 'source', 'profile_revision', 'started_at', 'completed_at', 'status')


def _validate_run(result: dict) -> None:
    """Validate our persisted boundary, including category-only failure payloads."""
    from datetime import datetime, timedelta
    from uuid import UUID
    from .discovery import build_discovery_plan, validate_budget
    from .work24_client import Work24Error
    from .models import DiscoveryRun

    if set(result) != set(DiscoveryRun.__annotations__):
        raise ValueError('Unexpected discovery fields')
    for failure in result['query_failures']:
        if set(failure) != {'query', 'reason'}:
            raise ValueError('Unexpected query failure fields')
    for failure in result['detail_failures']:
        if set(failure) != {'source', 'posting_id', 'reason'}:
            raise ValueError('Unexpected detail failure fields')
    if any(set(m) != {'source', 'posting_id', 'was_new', 'queries'} for m in result['postings']):
        raise ValueError('Unexpected membership fields')
    UUID(result['run_id'])
    if result['source'] != 'work24' or type(result['profile_revision']) is not int or result['profile_revision'] < 1:
        raise ValueError('Invalid discovery source or revision')
    times = [datetime.fromisoformat(result[key]) for key in ('started_at', 'completed_at')]
    if any(time.utcoffset() != timedelta(0) for time in times) or times[1] < times[0]:
        raise ValueError('Discovery times must be ordered UTC timestamps')
    validate_budget(result['pages'], result['display'], result['max_details'])
    if type(result['refresh_existing_details']) is not bool:
        raise ValueError('Invalid detail refresh option')
    plan = build_discovery_plan({'target_roles': result['plan']['target_roles']})
    if result['plan'] != plan or plan['status'] != 'ready':
        raise ValueError('Invalid discovery plan')
    queries = [q['keyword'] for q in plan['queries']]
    for field in ('query_successes', 'list_result_count', 'details_saved', 'details_reused', 'details_deferred', 'new_postings'):
        if type(result[field]) is not int or result[field] < 0:
            raise ValueError('Invalid discovery count')
    failed_queries = [f['query'] for f in result['query_failures']]
    if len(set(failed_queries)) != len(failed_queries) or not set(failed_queries) <= set(queries):
        raise ValueError('Invalid failed query identities')
    if result['query_successes'] + len(failed_queries) != len(queries):
        raise ValueError('Inconsistent query count')
    for failure in result['query_failures'] + result['detail_failures']:
        if failure['reason'] != Work24Error(failure['reason']).kind:
            raise ValueError('Unsafe discovery failure category')
    identities = [(m['source'], m['posting_id']) for m in result['postings']]
    if len(set(identities)) != len(identities):
        raise ValueError('Duplicate run membership')
    for member in result['postings']:
        storage.validate_identity(member['source'], member['posting_id'])
        if member['source'] != 'work24' or type(member['was_new']) is not bool:
            raise ValueError('Invalid discovery membership')
        terms = member['queries']
        if not terms or len(set(terms)) != len(terms) or not set(terms) <= set(queries) - set(failed_queries):
            raise ValueError('Invalid posting query provenance')
    failed_details = [(f['source'], f['posting_id']) for f in result['detail_failures']]
    if len(set(failed_details)) != len(failed_details) or not set(failed_details) <= set(identities):
        raise ValueError('Invalid failed detail identities')
    attempts = result['details_saved'] + len(failed_details)
    if (attempts > result['max_details'] or attempts + result['details_reused'] + result['details_deferred'] != len(identities)
            or result['new_postings'] != sum(m['was_new'] for m in result['postings'])
            or result['list_result_count'] < len(identities)):
        raise ValueError('Inconsistent discovery counts')
    expected = 'failed' if not result['query_successes'] else 'partial' if failed_queries or failed_details else 'completed'
    if result['status'] != expected or (expected == 'failed' and identities):
        raise ValueError('Inconsistent discovery status')


def _insert_run(conn, result: dict) -> None:
    import json
    _validate_run(result)
    report = {key: value for key, value in result.items() if key not in (*RUN_COLUMNS, 'postings')}
    conn.execute('INSERT INTO discovery_runs VALUES (?, ?, ?, ?, ?, ?, ?)',
                 tuple(result[key] for key in RUN_COLUMNS) + (json.dumps(report, ensure_ascii=False, allow_nan=False),))
    conn.executemany('INSERT INTO discovery_run_postings VALUES (?, ?, ?, ?, ?)',
                     [(result['run_id'], m['source'], m['posting_id'], int(m['was_new']),
                       json.dumps(m['queries'], ensure_ascii=False)) for m in result['postings']])


def load_discovery_run(path: Path, run_id: str | None = None) -> dict | None:
    """Latest completion, stable UUID tie-break. Historical membership, current raw data."""
    import json
    with closing(storage.connect(path)) as conn:
        storage.ensure_schema(conn)
        with conn:
            conn.execute('BEGIN')
            row = conn.execute('SELECT * FROM discovery_runs WHERE run_id=?', (run_id,)).fetchone() if run_id else conn.execute(
                'SELECT * FROM discovery_runs ORDER BY completed_at DESC, run_id DESC LIMIT 1').fetchone()
            if row is None:
                return None
            result = {**dict(zip(RUN_COLUMNS, row[:6])), **json.loads(row[6])}
            result['postings'] = [{'source': source, 'posting_id': pid, 'was_new': bool(was_new), 'queries': json.loads(terms)}
                                  for source, pid, was_new, terms in conn.execute(
                                      'SELECT source, posting_id, was_new, queries FROM discovery_run_postings WHERE run_id=? ORDER BY source, posting_id',
                                      (result['run_id'],))]
            return result


def list_discovery_runs(path: Path, *, limit: int = 20) -> list[dict]:
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('Run history limit must be between 1 and 100')
    with closing(storage.connect(path)) as conn:
        storage.ensure_schema(conn)
        return [dict(zip(RUN_COLUMNS, row)) for row in conn.execute(
            'SELECT run_id, source, profile_revision, started_at, completed_at, status FROM discovery_runs ORDER BY completed_at DESC, run_id DESC LIMIT ?', (limit,))]
