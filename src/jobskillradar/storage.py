from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from typing import cast

from .models import DETAIL_FIELDS, DETAIL_TEXT_FIELDS, JobPosting, POSTING_FIELDS, PostingDetail
from .migrations import enable_foreign_keys, ensure_schema, validate_identity
from .skill_extractor import extract_skills


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        enable_foreign_keys(conn)
    except BaseException:
        conn.close()
        raise
    return conn


def save_postings(conn: sqlite3.Connection, postings: list[dict]) -> int:
    """Replace full representations and derived skills atomically for the batch.

    Return only the number of new identities (updates still return zero).
    Missing optional fields replace previous values with NULL. Repeated identities
    in a direct batch use the last supplied representation. Preserve created_at.
    An existing caller transaction remains owned by that caller.
    """
    for posting in postings:
        validate_identity(posting.get("source"), posting.get("posting_id"))
    ensure_schema(conn)
    now = datetime.now().isoformat(timespec="seconds")
    columns = ", ".join((*POSTING_FIELDS, "created_at"))
    placeholders = ", ".join("?" for _ in range(len(POSTING_FIELDS) + 1))
    updates = ", ".join(f"{name}=excluded.{name}" for name in POSTING_FIELDS
                        if name not in ("source", "posting_id"))
    saved = 0
    conn.execute("SAVEPOINT save_postings_batch")
    try:
        for posting in postings:
            identity = (posting["source"], posting["posting_id"])
            exists = conn.execute(
                "SELECT 1 FROM job_postings WHERE source=? AND posting_id=?", identity
            ).fetchone()
            conn.execute(
                f"INSERT INTO job_postings ({columns}) VALUES ({placeholders}) "
                f"ON CONFLICT(source, posting_id) DO UPDATE SET {updates}",
                tuple(posting.get(name) for name in POSTING_FIELDS) + (now,),
            )
            saved += int(exists is None)
            # Read the actual persisted representation, including SQLite TEXT affinity.
            title, description = conn.execute(
                "SELECT title, description FROM job_postings WHERE source=? AND posting_id=?", identity
            ).fetchone()
            skills = extract_skills(title, description)
            conn.execute("DELETE FROM posting_skills WHERE source=? AND posting_id=?", identity)
            conn.executemany(
                "INSERT INTO posting_skills (source, posting_id, skill) VALUES (?, ?, ?)",
                [(*identity, skill) for skill in skills],
            )
        conn.execute("RELEASE SAVEPOINT save_postings_batch")
    except BaseException:
        conn.execute("ROLLBACK TO SAVEPOINT save_postings_batch")
        conn.execute("RELEASE SAVEPOINT save_postings_batch")
        raise
    return saved


def load_postings(conn: sqlite3.Connection) -> list[JobPosting]:
    ensure_schema(conn)
    rows = conn.execute(
        """
        SELECT source, posting_id, company, title, description, region, career,
               education, salary_type, salary, job_code, registered_at, closing_at, url
        FROM job_postings
        ORDER BY registered_at DESC, posting_id DESC, source ASC
        """
    ).fetchall()
    return [cast(JobPosting, dict(zip(POSTING_FIELDS, row))) for row in rows]


def count_postings(conn: sqlite3.Connection) -> int:
    ensure_schema(conn)
    row = conn.execute("SELECT COUNT(*) FROM job_postings").fetchone()
    return int(row[0])


def load_postings_from_db(db_path: Path) -> list[JobPosting]:
    """Own the connection lifetime; retain legacy schema-on-read behavior."""
    with closing(connect(db_path)) as conn:
        return load_postings(conn)


def save_postings_to_db(db_path: Path, postings: list[dict]) -> int:
    """Save one atomic batch and always close the connection."""
    with closing(connect(db_path)) as conn:
        return save_postings(conn, postings)


def save_posting_details(conn: sqlite3.Connection, details: list[PostingDetail]) -> None:
    """Atomically replace successful evidence; never accept a failure placeholder.

    Omitted optional text becomes NULL. Successful identical refreshes update only
    fetched_at when a new timestamp is supplied. Preserve the caller transaction.
    """
    rows = []
    for detail in details:
        validate_identity(detail.get("source"), detail.get("posting_id"))
        fetched_at = detail.get("fetched_at")
        if not isinstance(fetched_at, str) or not fetched_at.strip():
            raise ValueError("fetched_at must be a UTC ISO 8601 timestamp")
        try:
            offset = datetime.fromisoformat(fetched_at).utcoffset()
        except ValueError:
            raise ValueError("fetched_at must be a UTC ISO 8601 timestamp") from None
        if offset != timedelta(0):
            raise ValueError("fetched_at must be a UTC ISO 8601 timestamp")
        for name in DETAIL_TEXT_FIELDS:
            if detail.get(name) is not None and not isinstance(detail[name], str):
                raise ValueError(f"{name} must be text or None")
        keywords = detail.get("keywords")
        if not isinstance(keywords, list) or any(not isinstance(word, str) for word in keywords):
            raise ValueError("keywords must be a list of strings")
        values = {**detail, "keywords": json.dumps(keywords, ensure_ascii=False)}
        rows.append(tuple(values.get(name) for name in DETAIL_FIELDS))
    ensure_schema(conn)
    columns = ", ".join(DETAIL_FIELDS)
    placeholders = ", ".join("?" for _ in DETAIL_FIELDS)
    updates = ", ".join(f"{name}=excluded.{name}" for name in DETAIL_FIELDS
                        if name not in ("source", "posting_id"))
    conn.execute("SAVEPOINT save_details_batch")
    try:
        conn.executemany(
            f"INSERT INTO posting_details ({columns}) VALUES ({placeholders}) "
            f"ON CONFLICT(source, posting_id) DO UPDATE SET {updates}", rows,
        )
        conn.execute("RELEASE SAVEPOINT save_details_batch")
    except BaseException:
        conn.execute("ROLLBACK TO SAVEPOINT save_details_batch")
        conn.execute("RELEASE SAVEPOINT save_details_batch")
        raise


def load_posting_detail(conn: sqlite3.Connection, source: str, posting_id: str) -> PostingDetail | None:
    """None means never successfully stored; nullable fields mean source absence."""
    validate_identity(source, posting_id)
    ensure_schema(conn)
    row = conn.execute(
        f"SELECT {', '.join(DETAIL_FIELDS)} FROM posting_details WHERE source=? AND posting_id=?",
        (source, posting_id),
    ).fetchone()
    if row is None:
        return None
    detail = dict(zip(DETAIL_FIELDS, row))
    detail["keywords"] = json.loads(detail["keywords"])
    return cast(PostingDetail, detail)


def save_posting_details_to_db(db_path: Path, details: list[PostingDetail]) -> None:
    with closing(connect(db_path)) as conn:
        save_posting_details(conn, details)


def load_posting_detail_from_db(db_path: Path, source: str, posting_id: str) -> PostingDetail | None:
    with closing(connect(db_path)) as conn:
        return load_posting_detail(conn, source, posting_id)


def save_manual_bundle_to_db(db_path: Path, posting: JobPosting, detail: PostingDetail, *, create: bool) -> None:
    """Own one atomic manual-only create/edit, including collision/existence checks."""
    identity = (posting.get("source"), posting.get("posting_id"))
    validate_identity(*identity)
    if identity[0] != "manual" or identity != (detail.get("source"), detail.get("posting_id")):
        raise ValueError("Only matching manual posting identities can be saved")
    with closing(connect(db_path)) as conn:
        ensure_schema(conn)
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            exists = conn.execute("SELECT 1 FROM job_postings WHERE source=? AND posting_id=?", identity).fetchone()
            if create and exists:
                raise ValueError("Manual posting identity already exists")
            if not create and not exists:
                raise ValueError("Manual posting does not exist")
            save_postings(conn, [posting])
            save_posting_details(conn, [detail])


def load_posting_bundle_from_db(db_path: Path, source: str, posting_id: str) -> tuple[JobPosting, PostingDetail | None]:
    """Read metadata and detail from one SQLite snapshot; close before derivation."""
    validate_identity(source, posting_id)
    with closing(connect(db_path)) as conn:
        ensure_schema(conn)
        with conn:
            conn.execute("BEGIN")
            row = conn.execute(f"SELECT {', '.join(POSTING_FIELDS)} FROM job_postings WHERE source=? AND posting_id=?",
                               (source, posting_id)).fetchone()
            if row is None:
                raise ValueError("Posting does not exist")
            return cast(JobPosting, dict(zip(POSTING_FIELDS, row))), load_posting_detail(conn, source, posting_id)
