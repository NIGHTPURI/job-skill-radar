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


class DetailEvidence(TypedDict):
    """Source text, not interpreted requirements or normalized list metadata.

    Missing/blank optional XML values are None; keywords preserve source order.
    Neither this evidence nor its keywords feed skill extraction in Phase 3A.
    """

    source: str
    posting_id: str
    job_content: str | None
    employment_type: str | None
    raw_career_condition: str | None
    education: str | None
    foreign_language: str | None
    major: str | None
    certificate: str | None
    computer_skill: str | None
    preferred_conditions: str | None
    other_preferred_conditions: str | None
    selection_method: str | None
    receipt_method: str | None
    submit_documents: str | None
    other_information: str | None
    work_region: str | None
    work_hours: str | None
    welfare: str | None
    salary_condition: str | None
    closing_at: str | None
    detail_url: str | None
    keywords: list[str]


class PostingDetail(DetailEvidence):
    fetched_at: str  # UTC ISO 8601; added only after a successful fetch.


DETAIL_TEXT_FIELDS = tuple(
    name for name in DetailEvidence.__annotations__
    if name not in ("source", "posting_id", "keywords")
)
DETAIL_FIELDS = ("source", "posting_id", *DETAIL_TEXT_FIELDS, "keywords", "fetched_at")


class DetailFailure(TypedDict):
    source: str
    posting_id: str
    reason: str  # Safe category, never a request URL, key or response body.


class CollectionResult(TypedDict):
    collected: int
    new_postings: int
    details_saved: int
    detail_failures: list[DetailFailure]


RequirementType = Literal["required", "preferred", "responsibility", "unspecified"]
RequirementQuality = Literal[
    "detail_not_fetched",
    "detail_fetched_but_no_requirement_evidence",
    "requirements_extracted",
    "requirement_evidence_present_but_unclassified",
]


class RequirementEvidence(TypedDict):
    source_field: str
    source_index: int | None  # Index within keywords; None for scalar fields.
    evidence_text: str
    evidence_start: int  # Python string slice offsets, not byte or skill offsets.
    evidence_end: int
    section_heading: str | None
    section_start: int | None
    requirement_type: RequirementType
    rule: str  # Stable explanation code; never a probability.


class SkillRequirement(TypedDict):
    skill: str
    requirement_type: RequirementType
    evidence: list[RequirementEvidence]


class SourceCondition(TypedDict):
    source_field: str
    raw_text: str | None
    status: Literal["missing", "not_interpreted", "normalized"]
    normalized_value: str | None


class RequirementExtraction(TypedDict):
    extractor_version: int
    source: str | None
    posting_id: str | None
    detail_fetched_at: str | None
    quality_status: RequirementQuality
    skills: list[SkillRequirement]
    unclassified_evidence: list[RequirementEvidence]
    conditions: list[SourceCondition]
