"""Manual-source validation and raw capture, without I/O or technology inference."""
from __future__ import annotations

from urllib.parse import urlsplit

from .models import DETAIL_TEXT_FIELDS, JobPosting, PostingDetail
from .normalizer import clean_posting


def build_manual_posting(posting_id: str, captured_at: str, *, company: str, title: str, body: str,
                         url: str = "", region: str = "", career: str = "", education: str = "",
                         closing_at: str = "") -> tuple[JobPosting, PostingDetail]:
    values = locals()
    for field in ("company", "title", "body"):
        if not isinstance(values[field], str) or not values[field].strip():
            raise ValueError(f"{field} must be non-blank text")
    for field in ("url", "region", "career", "education", "closing_at"):
        if not isinstance(values[field], str):
            raise ValueError(f"{field} must be text")
    if url.strip():
        parsed = urlsplit(url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must be an absolute HTTP or HTTPS URL")
    posting = clean_posting({
        "source": "manual", "posting_id": posting_id, "company": company, "title": title,
        "description": "", "url": url, "region": region, "career": career,
        "education": education, "closing_at": closing_at,
    })
    # fetched_at means successful local capture/update for manual, not an HTTP fetch.
    detail = {**dict.fromkeys(DETAIL_TEXT_FIELDS), "source": "manual", "posting_id": posting_id,
              "job_content": body, "raw_career_condition": career or None, "education": education or None,
              "work_region": region or None, "closing_at": closing_at or None, "detail_url": url.strip() or None,
              "keywords": [], "fetched_at": captured_at}
    return posting, detail
