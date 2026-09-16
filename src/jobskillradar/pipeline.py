from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .analyzer import analyze_postings
from .config import get_db_path
from .models import AnalysisResult, JobPosting
from .normalizer import clean_postings
from .sample_data import SAMPLE_POSTINGS
from .storage import load_postings_from_db, save_postings_to_db
from .work24_client import fetch_work24_postings


DEFAULT_KEYWORDS = [
    "데이터 분석가",
    "데이터 엔지니어",
    "머신러닝",
    "SQL",
    "Python",
]

# A collector accepts the keyword arguments of fetch_work24_postings.
# A callable is sufficient here; no provider class or repository is needed.
Collector = Callable[..., list[JobPosting]]


def analyze_sample() -> AnalysisResult:
    return analyze_postings(clean_postings(SAMPLE_POSTINGS))


def load_db_analysis(*, db_path: Path | None = None) -> AnalysisResult | None:
    postings = load_postings_from_db(get_db_path() if db_path is None else db_path)
    if not postings:
        return None
    return analyze_postings(clean_postings(postings))


def load_analysis(mode: str, *, db_path: Path | None = None) -> tuple[AnalysisResult, str]:
    """Select DB-first or sample data using the existing dashboard policy.

    An empty DB falls back to sample data. DB errors still propagate. Other
    mode strings retain the original sample-only behavior.
    """
    if mode == "DB 우선":
        db_analysis = load_db_analysis(db_path=db_path)
        if db_analysis:
            return db_analysis, "DB"
    return analyze_sample(), "샘플"


def seed_sample_db(*, db_path: Path | None = None) -> int:
    postings = clean_postings(SAMPLE_POSTINGS)
    return save_postings_to_db(get_db_path() if db_path is None else db_path, postings)


def collect_postings(
    auth_key: str,
    keywords: list[str] | None = None,
    pages: int = 1,
    display: int = 100,
    *,
    collector: Collector | None = None,
) -> list[JobPosting]:
    """Collect all keywords, then normalize and deduplicate before any write.

    Preserve first-identity-wins, default keywords for empty input, and all-or-error
    batch behavior. HTTP/XML and per-page behavior remain in the client.
    """
    fetch = fetch_work24_postings if collector is None else collector
    collected: list[JobPosting] = []
    for keyword in keywords or DEFAULT_KEYWORDS:
        collected.extend(
            fetch(
                auth_key=auth_key,
                keyword=keyword,
                pages=pages,
                display=display,
            )
        )

    return clean_postings(collected)


def collect_work24_to_db(
    auth_key: str,
    keywords: list[str] | None = None,
    pages: int = 1,
    display: int = 100,
    *,
    db_path: Path | None = None,
    collector: Collector | None = None,
) -> int:
    postings = collect_postings(auth_key, keywords, pages, display, collector=collector)
    return save_postings_to_db(get_db_path() if db_path is None else db_path, postings)


def collect_and_analyze(
    auth_key: str,
    keywords: list[str] | None = None,
    pages: int = 1,
    *,
    collector: Collector | None = None,
) -> AnalysisResult:
    return analyze_postings(collect_postings(auth_key, keywords, pages, collector=collector))
