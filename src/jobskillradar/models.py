"""Dictionary-compatible contracts; these types do not validate or coerce data.

Collectors and normalization produce all 14 base fields. Legacy callers may
provide partial dictionaries; SQLite rows may contain None. Generated fields
belong to analysis only. Keep absence distinct from an explicit None at runtime.
"""
from __future__ import annotations

from collections import Counter
from typing import Literal, TypedDict


class JobPosting(TypedDict, total=False):
    source: str | None
    posting_id: str | None
    company: str | None
    title: str | None
    description: str | None
    region: str | None
    career: str | None
    education: str | None
    salary_type: str | None
    salary: str | None
    job_code: str | None
    registered_at: str | None
    closing_at: str | None
    url: str | None
    skills: list[str]
    role: str


# Declaration order is the existing normalized/SELECT field order.
# created_at is storage-owned and intentionally absent from this contract.
GENERATED_POSTING_FIELDS = ("skills", "role")
POSTING_FIELDS = tuple(
    name for name in JobPosting.__annotations__ if name not in GENERATED_POSTING_FIELDS
)


class AnalysisResult(TypedDict):
    postings: list[JobPosting]
    skill_counts: Counter[str]
    role_counts: Counter[str]
    career_counts: Counter[str | None]
    region_counts: Counter[str | None]
    role_skill_counts: dict[str, Counter[str]]


class SkillRecommendation(TypedDict):
    """Learning order and observable evidence, never a hiring or fit score."""

    skill: str
    priority: int
    market_count: int
    role_posting_count: int | None
    is_foundation: bool
    evidence_source: Literal["role_market", "foundation_only"]
    reason: str
