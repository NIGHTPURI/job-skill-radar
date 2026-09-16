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
    return result
