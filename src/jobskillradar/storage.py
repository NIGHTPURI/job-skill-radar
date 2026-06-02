from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from .skill_extractor import extract_skills


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(db_path)


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS job_postings (
            posting_id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            company TEXT,
            title TEXT,
            description TEXT,
            region TEXT,
            career TEXT,
            education TEXT,
            salary_type TEXT,
            salary TEXT,
            job_code TEXT,
            registered_at TEXT,
            closing_at TEXT,
            url TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS posting_skills (
            posting_id TEXT NOT NULL,
            skill TEXT NOT NULL,
            PRIMARY KEY (posting_id, skill)
        )
        """
    )
    conn.commit()


def save_postings(conn: sqlite3.Connection, postings: list[dict]) -> int:
    ensure_schema(conn)
    now = datetime.now().isoformat(timespec="seconds")
    saved = 0
    for posting in postings:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO job_postings (
                posting_id, source, company, title, description, region, career,
                education, salary_type, salary, job_code, registered_at, closing_at,
                url, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                posting.get("posting_id"),
                posting.get("source"),
                posting.get("company"),
                posting.get("title"),
                posting.get("description"),
                posting.get("region"),
                posting.get("career"),
                posting.get("education"),
                posting.get("salary_type"),
                posting.get("salary"),
                posting.get("job_code"),
                posting.get("registered_at"),
                posting.get("closing_at"),
                posting.get("url"),
                now,
            ),
        )
        if cursor.rowcount:
            saved += 1
        for skill in extract_skills(posting.get("title"), posting.get("description")):
            conn.execute(
                "INSERT OR IGNORE INTO posting_skills (posting_id, skill) VALUES (?, ?)",
                (posting.get("posting_id"), skill),
            )
    conn.commit()
    return saved


def load_postings(conn: sqlite3.Connection) -> list[dict]:
    ensure_schema(conn)
    rows = conn.execute(
        """
        SELECT source, posting_id, company, title, description, region, career,
               education, salary_type, salary, job_code, registered_at, closing_at, url
        FROM job_postings
        ORDER BY registered_at DESC, posting_id DESC
        """
    ).fetchall()
    keys = [
        "source",
        "posting_id",
        "company",
        "title",
        "description",
        "region",
        "career",
        "education",
        "salary_type",
        "salary",
        "job_code",
        "registered_at",
        "closing_at",
        "url",
    ]
    return [dict(zip(keys, row)) for row in rows]


def count_postings(conn: sqlite3.Connection) -> int:
    ensure_schema(conn)
    row = conn.execute("SELECT COUNT(*) FROM job_postings").fetchone()
    return int(row[0])
