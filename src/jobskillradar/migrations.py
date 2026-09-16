"""Transactional SQLite upgrades v0 -> v1 -> v2 -> v3, with pre-migration backups."""
from __future__ import annotations

import logging
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from .models import DETAIL_FIELDS, POSTING_FIELDS
from .skill_extractor import extract_skills

SCHEMA_VERSION = 3
logger = logging.getLogger(__name__)


def enable_foreign_keys(conn: sqlite3.Connection) -> None:
    if conn.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        if conn.in_transaction:
            raise RuntimeError("Enable foreign keys before starting a transaction")
        conn.execute("PRAGMA foreign_keys = ON")
        if conn.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise RuntimeError("SQLite foreign key enforcement is unavailable")


def validate_identity(source: object, posting_id: object) -> None:
    for name, value in (("source", source), ("posting_id", posting_id)):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")


def _create_tables(conn: sqlite3.Connection, suffix: str = "") -> None:
    # suffix is internal, never derived from user input.
    conn.execute(f"""
        CREATE TABLE job_postings{suffix} (
            source TEXT NOT NULL CHECK(length(trim(source, char(9)||char(10)||char(13)||' ')) > 0),
            posting_id TEXT NOT NULL CHECK(length(trim(posting_id, char(9)||char(10)||char(13)||' ')) > 0),
            company TEXT, title TEXT, description TEXT, region TEXT, career TEXT,
            education TEXT, salary_type TEXT, salary TEXT, job_code TEXT,
            registered_at TEXT, closing_at TEXT, url TEXT,
            created_at TEXT NOT NULL,
            PRIMARY KEY (source, posting_id)
        )
    """)
    conn.execute(f"""
        CREATE TABLE posting_skills{suffix} (
            source TEXT NOT NULL,
            posting_id TEXT NOT NULL,
            skill TEXT NOT NULL,
            PRIMARY KEY (source, posting_id, skill),
            FOREIGN KEY (source, posting_id)
                REFERENCES job_postings{suffix}(source, posting_id) ON DELETE CASCADE
        )
    """)


def _check_layout(conn: sqlite3.Connection, version: int) -> None:
    expected = {
        "job_postings": (set(POSTING_FIELDS) | {"created_at"},
                         ["posting_id"] if version == 0 else ["source", "posting_id"]),
        "posting_skills": ({"posting_id", "skill"} if version == 0 else {"source", "posting_id", "skill"},
                           ["posting_id", "skill"] if version == 0 else ["source", "posting_id", "skill"]),
    }
    if version >= 2:
        expected["posting_details"] = (set(DETAIL_FIELDS), ["source", "posting_id"])
    if version >= 3:
        expected["user_profile"] = ({"singleton", "revision", "owned_skills", "target_roles",
                                     "preferred_regions", "required_regions"}, ["singleton"])
    for table, (names, primary_key) in expected.items():
        columns = conn.execute(f"PRAGMA table_info({table})").fetchall()
        keys = [row[1] for row in sorted(columns, key=lambda row: row[5]) if row[5]]
        if {row[1] for row in columns} != names or keys != primary_key:
            raise RuntimeError(f"Unsupported {table} layout; database left unchanged")
        if version >= 1:
            required = {
                "job_postings": {"source", "posting_id", "created_at"},
                "posting_skills": {"source", "posting_id", "skill"},
                "posting_details": {"source", "posting_id", "keywords", "fetched_at"},
                "user_profile": {"revision", "owned_skills", "target_roles", "preferred_regions", "required_regions"},
            }[table]
            if not required <= {row[1] for row in columns if row[3]}:
                raise RuntimeError(f"Missing NOT NULL constraints in {table}")
    if version >= 1:
        for table in (["posting_skills", "posting_details"] if version >= 2 else ["posting_skills"]):
            foreign_keys = conn.execute(f"PRAGMA foreign_key_list({table})").fetchall()
            if {(r[0], r[1], r[2], r[3], r[4], r[6]) for r in foreign_keys} != {
                (0, 0, "job_postings", "source", "source", "CASCADE"),
                (0, 1, "job_postings", "posting_id", "posting_id", "CASCADE"),
            }:
                raise RuntimeError(f"Invalid {table} foreign key")


def _create_detail_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE posting_details (
            source TEXT NOT NULL,
            posting_id TEXT NOT NULL,
            job_content TEXT, employment_type TEXT, raw_career_condition TEXT,
            education TEXT, foreign_language TEXT, major TEXT, certificate TEXT,
            computer_skill TEXT, preferred_conditions TEXT, other_preferred_conditions TEXT,
            selection_method TEXT, receipt_method TEXT, submit_documents TEXT,
            other_information TEXT, work_region TEXT, work_hours TEXT, welfare TEXT,
            salary_condition TEXT, closing_at TEXT, detail_url TEXT,
            keywords TEXT NOT NULL,
            fetched_at TEXT NOT NULL CHECK(length(trim(fetched_at)) > 0),
            PRIMARY KEY (source, posting_id),
            FOREIGN KEY (source, posting_id)
                REFERENCES job_postings(source, posting_id) ON DELETE CASCADE
        )
    """)


def _create_profile_table(conn: sqlite3.Connection) -> None:
    conn.execute("""CREATE TABLE user_profile (
        singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
        revision INTEGER NOT NULL CHECK(revision >= 1),
        owned_skills TEXT NOT NULL, target_roles TEXT NOT NULL,
        preferred_regions TEXT NOT NULL, required_regions TEXT NOT NULL
    )""")


def _backup_database(conn: sqlite3.Connection) -> Path | None:
    filename = next(row[2] for row in conn.execute("PRAGMA database_list") if row[1] == "main")
    if not filename:
        return None  # In-memory tests have no user file to back up.
    path = Path(filename)
    source_version = conn.execute("PRAGMA user_version").fetchone()[0]
    # Both the pending upgrade and the backed-up schema are explicit.
    prefix = path.name + f".pre-v{SCHEMA_VERSION}-from-v{source_version}-"
    with tempfile.NamedTemporaryFile(prefix=prefix, suffix=".bak", dir=path.parent, delete=False) as file:
        backup_path = Path(file.name)
    try:
        with closing(sqlite3.connect(backup_path)) as backup:
            conn.backup(backup)
    except BaseException:
        backup_path.unlink(missing_ok=True)  # Only the newly created incomplete backup.
        raise
    logger.warning("마이그레이션 전 DB 백업 완료: %s", backup_path)
    return backup_path


def _migrate_legacy(conn: sqlite3.Connection) -> tuple[int, int, int]:
    columns = ", ".join((*POSTING_FIELDS, "created_at"))
    rows = conn.execute(f"SELECT {columns} FROM job_postings").fetchall()
    for row in rows:
        validate_identity(row[0], row[1])
    orphan_count = conn.execute("""
        SELECT COUNT(*) FROM posting_skills s
        WHERE NOT EXISTS (SELECT 1 FROM job_postings p WHERE p.posting_id = s.posting_id)
    """).fetchone()[0]
    old_skills = set(conn.execute("""
        SELECT p.source, s.posting_id, s.skill FROM posting_skills s
        JOIN job_postings p ON p.posting_id = s.posting_id
    """).fetchall())
    _create_tables(conn, "_v1")
    conn.execute(f"INSERT INTO job_postings_v1 ({columns}) SELECT {columns} FROM job_postings")
    current_skills = {
        (row[0], row[1], skill)
        for row in rows for skill in extract_skills(row[3], row[4])
    }
    conn.executemany("INSERT INTO posting_skills_v1 VALUES (?, ?, ?)", sorted(current_skills))
    copied = conn.execute(f"SELECT {columns} FROM job_postings_v1").fetchall()
    if set(copied) != set(rows) or conn.execute("PRAGMA foreign_key_check(posting_skills_v1)").fetchall():
        raise RuntimeError("Migration validation failed")
    # Copy and validation precede dropping legacy tables. All DDL is transactional.
    conn.execute("DROP TABLE posting_skills")
    conn.execute("DROP TABLE job_postings")
    conn.execute("ALTER TABLE job_postings_v1 RENAME TO job_postings")
    conn.execute("ALTER TABLE posting_skills_v1 RENAME TO posting_skills")
    return orphan_count, len(old_skills - current_skills), len(current_skills - old_skills)


def ensure_schema(conn: sqlite3.Connection) -> None:
    enable_foreign_keys(conn)
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version == SCHEMA_VERSION:
        _check_layout(conn, version)
        return
    if version not in (0, 1, 2):
        raise RuntimeError(f"Unsupported schema version: {version}")
    if conn.in_transaction:
        raise RuntimeError("Schema initialization requires no active transaction")
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    legacy = version == 0 and bool(tables)
    if legacy:
        if tables != {"job_postings", "posting_skills"}:
            raise RuntimeError("Unrecognized legacy database; refusing migration")
        _check_layout(conn, 0)
        if conn.execute("SELECT 1 FROM sqlite_master WHERE type IN ('trigger','view') OR (type='index' AND sql IS NOT NULL)").fetchone():
            raise RuntimeError("Custom legacy schema objects require manual migration")
    elif version == 1:
        _check_layout(conn, 1)
        if "posting_details" in tables:
            raise RuntimeError("Unexpected posting_details table in v1; database left unchanged")
    elif version == 2:
        _check_layout(conn, 2)
    if "user_profile" in tables:
        raise RuntimeError("Unexpected user_profile table before v3; database left unchanged")
    if legacy or version in (1, 2):
        _backup_database(conn)
    conn.execute("BEGIN IMMEDIATE")
    report = None
    try:
        # Recheck after acquiring the write lock (another opener may have migrated).
        locked_version = conn.execute("PRAGMA user_version").fetchone()[0]
        if locked_version == SCHEMA_VERSION:
            _check_layout(conn, SCHEMA_VERSION)
        else:
            if locked_version not in (0, 1, 2):
                raise RuntimeError(f"Unsupported schema version: {locked_version}")
            if locked_version == 0:
                if legacy:
                    report = _migrate_legacy(conn)
                else:
                    _create_tables(conn)
            if locked_version <= 1:
                _check_layout(conn, 1)
                # v1 -> v2 is additive: do not rewrite postings, skills or created_at.
                _create_detail_table(conn)
            _check_layout(conn, 2)
            # v2 -> v3 is additive; all raw posting data stays untouched.
            _create_profile_table(conn)
            _check_layout(conn, SCHEMA_VERSION)
            if conn.execute("PRAGMA foreign_key_check").fetchall():
                raise RuntimeError("Foreign key validation failed")
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    if report is not None:
        logger.warning("DB v1 이전 완료: 부모 없는 기술 %d건 제외, 본문 불일치 기술 %d건 제거, 누락 기술 %d건 복원", *report)
