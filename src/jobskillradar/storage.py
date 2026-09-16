from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import cast

from .models import JobPosting, POSTING_FIELDS
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
