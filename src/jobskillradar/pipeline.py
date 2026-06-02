from __future__ import annotations

from .analyzer import analyze_postings
from .config import get_db_path
from .normalizer import clean_postings
from .sample_data import SAMPLE_POSTINGS
from .storage import connect, load_postings, save_postings
from .work24_client import fetch_work24_postings


DEFAULT_KEYWORDS = [
    "데이터 분석가",
    "데이터 엔지니어",
    "머신러닝",
    "SQL",
    "Python",
]


def analyze_sample() -> dict:
    return analyze_postings(clean_postings(SAMPLE_POSTINGS))


def load_db_analysis() -> dict | None:
    conn = connect(get_db_path())
    try:
        postings = load_postings(conn)
    finally:
        conn.close()
    if not postings:
        return None
    return analyze_postings(clean_postings(postings))


def seed_sample_db() -> int:
    postings = clean_postings(SAMPLE_POSTINGS)
    conn = connect(get_db_path())
    try:
        return save_postings(conn, postings)
    finally:
        conn.close()


def collect_work24_to_db(
    auth_key: str,
    keywords: list[str] | None = None,
    pages: int = 1,
    display: int = 100,
) -> int:
    collected = []
    for keyword in keywords or DEFAULT_KEYWORDS:
        collected.extend(
            fetch_work24_postings(
                auth_key=auth_key,
                keyword=keyword,
                pages=pages,
                display=display,
            )
        )

    postings = clean_postings(collected)
    conn = connect(get_db_path())
    try:
        return save_postings(conn, postings)
    finally:
        conn.close()


def collect_and_analyze(auth_key: str, keywords: list[str] | None = None, pages: int = 1) -> dict:
    collected = []
    for keyword in keywords or DEFAULT_KEYWORDS:
        collected.extend(fetch_work24_postings(auth_key=auth_key, keyword=keyword, pages=pages))
    return analyze_postings(clean_postings(collected))
