"""Singleton profile persistence, separate from posting/raw evidence storage."""
from __future__ import annotations

import json
from contextlib import closing
from pathlib import Path

from .migrations import ensure_schema
from .models import LocalProfile, ProfileValues
from .profile import PROFILE_FIELDS, normalize_profile
from .storage import connect


def _read_profile(conn) -> LocalProfile | None:
    row = conn.execute(f"SELECT revision, {', '.join(PROFILE_FIELDS)} FROM user_profile WHERE singleton=1").fetchone()
    if row is None:
        return None
    fields = {field: json.loads(value) for field, value in zip(PROFILE_FIELDS, row[1:])}
    # Corrupt external edits fail visibly instead of masquerading as an empty profile.
    return {**normalize_profile(**fields), "revision": row[0]}


def load_profile_from_db(db_path: Path) -> LocalProfile | None:
    with closing(connect(db_path)) as conn:
        ensure_schema(conn)
        return _read_profile(conn)


def save_profile_to_db(db_path: Path, values: ProfileValues) -> LocalProfile:
    normalized = normalize_profile(**values)
    with closing(connect(db_path)) as conn:
        ensure_schema(conn)
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            previous = _read_profile(conn)
            if previous is not None and all(previous[field] == normalized[field] for field in PROFILE_FIELDS):
                return previous
            revision = previous["revision"] + 1 if previous else 1
            conn.execute(f"""INSERT INTO user_profile (singleton, revision, {', '.join(PROFILE_FIELDS)})
                VALUES (1, ?, ?, ?, ?, ?) ON CONFLICT(singleton) DO UPDATE SET
                revision=excluded.revision, {', '.join(f'{field}=excluded.{field}' for field in PROFILE_FIELDS)}""",
                (revision, *(json.dumps(normalized[field], ensure_ascii=False) for field in PROFILE_FIELDS)))
            return {**normalized, "revision": revision}
