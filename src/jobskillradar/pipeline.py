from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

from .analyzer import analyze_postings, enrich_posting
from .config import get_db_path
from .models import AnalysisResult, CollectionResult, JobComparison, JobPosting, LocalProfile, PostingDetail, RequirementExtraction
from .normalizer import clean_postings
from .sample_data import SAMPLE_POSTINGS
from .requirement_extractor import extract_requirements
from .manual_postings import build_manual_posting
from .profile import normalize_profile
from .profile_storage import load_profile_from_db, save_profile_to_db
from .matcher import compare_profile_to_requirements
from .storage import load_posting_bundle_from_db, save_manual_bundle_to_db
from .storage import load_posting_detail_from_db, load_postings_from_db, save_posting_details_to_db, save_postings_to_db
from .work24_client import Work24Error, fetch_posting_detail, fetch_work24_postings


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
DetailFetcher = Callable[..., PostingDetail]


def load_posting_requirements(
    source: str, posting_id: str, *, db_path: Path | None = None,
) -> RequirementExtraction:
    """Derive on demand after the detail reader has closed its DB connection.

    No HTTP, derived cache, or writes to posting data. Unexpected extraction
    failures propagate and cannot overwrite raw detail or a previous result.
    The existing storage reader still ensures the schema on first open.
    """
    detail = load_posting_detail_from_db(get_db_path() if db_path is None else db_path, source, posting_id)
    result = extract_requirements(detail)
    return {**result, "source": source, "posting_id": posting_id}


def analyze_sample() -> AnalysisResult:
    return analyze_postings(clean_postings(SAMPLE_POSTINGS))


def load_db_analysis(*, db_path: Path | None = None, sources: tuple[str, ...] | None = None) -> AnalysisResult | None:
    postings = load_postings_from_db(get_db_path() if db_path is None else db_path)
    # Manual selections are individual review material, never implicit market data.
    postings = [p for p in postings if p["source"] != "manual" and (sources is None or p["source"] in sources)]
    if not postings:
        return None
    return analyze_postings(clean_postings(postings))


def load_market_analysis(mode: str, *, db_path: Path | None = None) -> tuple[AnalysisResult, str]:
    """Dashboard scope: Work24 only; otherwise explicitly labeled sample data."""
    if mode == "DB 우선":
        analysis = load_db_analysis(db_path=db_path, sources=("work24",))
        if analysis is not None:
            return analysis, "고용24"
    return analyze_sample(), "샘플"


def list_saved_postings(*, db_path: Path | None = None) -> list[JobPosting]:
    return load_postings_from_db(get_db_path() if db_path is None else db_path)


def load_posting_review(source: str, posting_id: str, *, db_path: Path | None = None) -> dict:
    posting, detail = load_posting_bundle_from_db(get_db_path() if db_path is None else db_path, source, posting_id)
    extraction = extract_requirements(detail)
    return {"posting": posting, "detail": detail,
            "requirements": {**extraction, "source": source, "posting_id": posting_id}}


def create_manual_posting(*, db_path: Path | None = None, id_factory: Callable[[], str] | None = None,
                          captured_at: str | None = None, **fields) -> str:
    posting_id = str(uuid4()) if id_factory is None else id_factory()
    posting, detail = build_manual_posting(posting_id, captured_at or datetime.now(timezone.utc).isoformat(), **fields)
    save_manual_bundle_to_db(get_db_path() if db_path is None else db_path, posting, detail, create=True)
    return posting_id


def update_manual_posting(source: str, posting_id: str, *, db_path: Path | None = None,
                          captured_at: str | None = None, **fields) -> None:
    if source != "manual":
        raise ValueError("Only manual postings can be edited")
    posting, detail = build_manual_posting(posting_id, captured_at or datetime.now(timezone.utc).isoformat(), **fields)
    save_manual_bundle_to_db(get_db_path() if db_path is None else db_path, posting, detail, create=False)


def load_profile(*, db_path: Path | None = None) -> LocalProfile | None:
    return load_profile_from_db(get_db_path() if db_path is None else db_path)


def save_profile(*, db_path: Path | None = None, **fields) -> LocalProfile:
    values = normalize_profile(**fields)
    return save_profile_to_db(get_db_path() if db_path is None else db_path, values)


def load_posting_comparison(source: str, posting_id: str, *, db_path: Path | None = None) -> JobComparison:
    """Recompute using current stored declarations and raw evidence, after closing DB readers."""
    profile = load_profile(db_path=db_path)
    if profile is None:
        raise ValueError("Save a local profile before comparison")
    review = load_posting_review(source, posting_id, db_path=db_path)
    role = enrich_posting(review["posting"])["role"]
    return compare_profile_to_requirements(profile, review["requirements"], posting_role=role)


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


def collect_work24_with_details_to_db(
    auth_key: str,
    keywords: list[str] | None = None,
    pages: int = 1,
    display: int = 100,
    *,
    db_path: Path | None = None,
    collector: Collector | None = None,
    detail_fetcher: DetailFetcher | None = None,
) -> CollectionResult:
    """Explicitly refresh each collected Work24 identity once, without a TTL.

    Commit the atomic list batch first. Fetch with no DB connection open; commit
    each successful detail separately. Expected detail failures retain prior
    evidence and do not prevent other requests. DB/programming errors propagate.
    The list-only entry point keeps its int return and makes no detail requests.
    """
    postings = collect_postings(auth_key, keywords, pages, display, collector=collector)
    path = get_db_path() if db_path is None else db_path
    result: CollectionResult = {
        "collected": len(postings), "new_postings": save_postings_to_db(path, postings),
        "details_saved": 0, "detail_failures": [],
    }
    fetch = fetch_posting_detail if detail_fetcher is None else detail_fetcher
    # collect_postings already deduplicated using (source, posting_id).
    for posting in postings:
        source, posting_id = posting["source"], posting["posting_id"]
        try:
            if source != "work24":
                raise Work24Error("unsupported_source")
            detail = fetch(auth_key=auth_key, wanted_auth_no=posting_id)
            if (detail["source"], detail["posting_id"]) != (source, posting_id):
                raise Work24Error("identity_mismatch")
        except Work24Error as error:
            result["detail_failures"].append({
                "source": source, "posting_id": posting_id, "reason": error.kind,
            })
            continue
        save_posting_details_to_db(path, [detail])
        result["details_saved"] += 1
    return result
