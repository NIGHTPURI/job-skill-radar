"""Sequential discovery orchestration, separate from market analysis and pure planning."""
from __future__ import annotations

from datetime import datetime, timezone
from http.client import HTTPException
from uuid import uuid4

from .config import get_db_path
from .discovery import (DEFAULT_DISPLAY, DEFAULT_MAX_DETAILS, DEFAULT_PAGES,
                        build_discovery_plan, validate_budget)
from .discovery_storage import load_discovery_state, save_discovery_batch
from .models import DiscoveryRun
from .normalizer import clean_postings
from .pipeline import load_profile
from .work24_client import Work24Error, fetch_posting_detail, fetch_work24_postings


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _failure_category(error: Exception) -> str:
    return Work24Error(error.kind).kind if isinstance(error, Work24Error) else "transport_error"


def discover_work24_jobs(auth_key: str, *, db_path=None, pages=DEFAULT_PAGES,
                         display=DEFAULT_DISPLAY, max_details=DEFAULT_MAX_DETAILS,
                         refresh_existing_details=False, collector=None, detail_fetcher=None,
                         progress=None) -> DiscoveryRun:
    """Network first, then one small atomic save; no retry or unbounded pagination.

    Expected request failures are categories only. Unexpected programming/storage
    failures propagate, never masquerading as valid empty evidence. Budget-deferred
    details are explicit, not failures. Successful empty list queries are valid.
    """
    validate_budget(pages, display, max_details)
    if type(refresh_existing_details) is not bool:
        raise ValueError("refresh_existing_details must be boolean")
    if not isinstance(auth_key, str) or not auth_key.strip():
        raise ValueError("WORK24_AUTH_KEY is required")
    path = get_db_path() if db_path is None else db_path
    profile = load_profile(db_path=path)
    plan = build_discovery_plan(profile)
    if plan["status"] != "ready":
        raise ValueError("Save a profile with target roles before discovery")
    known, detailed = load_discovery_state(path)
    result = {"run_id": str(uuid4()), "source": "work24", "profile_revision": profile["revision"],
              "started_at": _now(), "completed_at": None, "status": "completed", "plan": plan,
              "pages": pages, "display": display, "max_details": max_details,
              "refresh_existing_details": refresh_existing_details,
              "list_result_count": 0, "query_successes": 0, "query_failures": [],
              "details_saved": 0, "detail_failures": [], "details_reused": 0,
              "details_deferred": 0, "new_postings": 0, "postings": []}
    fetch_list = fetch_work24_postings if collector is None else collector
    fetch_detail = fetch_posting_detail if detail_fetcher is None else detail_fetcher
    by_id = {}
    members = {}
    for index, query in enumerate(plan["queries"]):
        if progress:
            progress("query", index + 1, len(plan["queries"]))
        try:
            raw = fetch_list(auth_key=auth_key, keyword=query["keyword"], pages=pages, display=display)
            cleaned = clean_postings(raw)
            # A provider boundary must not admit manual/sample data or unidentified rows.
            if any(p["source"] != "work24" for p in cleaned) or any(
                    not str(p.get("posting_id", "") or "").strip() for p in raw):
                raise Work24Error("unexpected_structure")
        except (Work24Error, OSError, HTTPException) as error:
            result["query_failures"].append({"query": query["keyword"], "reason": _failure_category(error)})
            continue
        result["query_successes"] += 1
        result["list_result_count"] += len(raw)
        for posting in cleaned:
            identity = posting["posting_id"]
            if identity not in by_id:
                by_id[identity] = posting
                members[identity] = {"source": "work24", "posting_id": identity,
                                     "queries": [], "was_new": False}
            members[identity]["queries"].append(query["keyword"])
    # Preserve query/source order within each priority; unknown and missing before refresh.
    candidates = sorted(by_id, key=lambda pid: (pid in known, pid in detailed))
    details = []
    attempted = 0
    for posting_id in candidates:
        if posting_id in detailed and not refresh_existing_details:
            result["details_reused"] += 1
            continue
        if attempted >= max_details:
            result["details_deferred"] += 1
            continue
        attempted += 1
        if progress:
            progress("detail", attempted, min(max_details, len(candidates)))
        try:
            detail = fetch_detail(auth_key=auth_key, wanted_auth_no=posting_id)
            if (detail.get("source"), detail.get("posting_id")) != ("work24", posting_id):
                raise Work24Error("identity_mismatch")
        except (Work24Error, OSError, HTTPException) as error:
            result["detail_failures"].append({"source": "work24", "posting_id": posting_id,
                                              "reason": _failure_category(error)})
            continue
        details.append(detail)
    result["details_saved"] = len(details)
    result["postings"] = list(members.values())
    if not result["query_successes"]:
        result["status"] = "failed"
    elif result["query_failures"] or result["detail_failures"]:
        result["status"] = "partial"
    result["completed_at"] = _now()
    return save_discovery_batch(path, result, list(by_id.values()), details)
