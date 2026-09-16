"""Pure, conservative comparison of profile declarations and source evidence.

Missing from a profile does not mean unknown to the person. There is no score,
ranking, aggregate candidate verdict, I/O or inference of skill ecosystems.
"""
from __future__ import annotations

from copy import deepcopy

from .models import JobComparison, LocalProfile, RequirementEvidence, RequirementExtraction, RequirementType
from .profile import PROFILE_FIELDS, REGIONS, normalize_profile
from .requirement_extractor import REQUIREMENT_PRECEDENCE
from .role_classifier import ROLE_LABELS, UNKNOWN


def independent_requirement_type(evidence: list[RequirementEvidence]) -> RequirementType | None:
    """Project only independent occurrences; grouped members are shown as groups."""
    kinds = [item["requirement_type"] for item in evidence if item["relation"] == "independent"]
    return min(kinds, key=REQUIREMENT_PRECEDENCE.__getitem__) if kinds else None


def _compare_conditions(profile: dict, conditions: list[dict]) -> list[dict]:
    results = []
    by_field = {condition["source_field"]: condition for condition in conditions}
    for field in ("raw_career_condition", "education", "employment_type", "work_region"):
        raw = by_field.get(field, {}).get("raw_text")
        policies = []
        if field == "work_region":
            policies = [(policy, profile[key]) for policy, key in
                        (("required", "required_regions"), ("preferred", "preferred_regions")) if profile[key]]
        for policy, expected in policies or [("not_configured", [])]:
            status, reason = "unknown", "profile_condition_not_configured"
            if raw is None or not raw.strip():
                reason = "posting_condition_missing"
            elif policy != "not_configured":
                # Exact complete labels only: no substring/geography/commuting inference.
                if raw.strip() not in REGIONS:
                    reason = "posting_condition_not_interpreted"
                else:
                    present = raw.strip() in expected
                    status = ("satisfied" if present else "not_satisfied") if policy == "required" else (
                        "preference_match" if present else "preference_mismatch")
                    reason = "exact_region_label"
            results.append({"source_field": field, "raw_text": raw, "policy": policy,
                            "expected_values": list(expected), "status": status, "reason": reason})
    return results


def compare_profile_to_requirements(profile: LocalProfile, extraction: RequirementExtraction,
                                    *, posting_role: str | None = None) -> JobComparison:
    """Compare independent evidence and groups separately, without double counting.

    The effective independent class uses the extractor's precedence restricted
    to independent evidence. Group-only occurrences never create separate skill
    gaps. All original skill evidence remains attached for source audit/review.
    """
    if profile is None or type(profile.get("revision")) is not int or profile["revision"] < 1:
        raise ValueError("A saved profile with a positive revision is required")
    if extraction["extractor_version"] != 2:
        raise ValueError("Comparison requires the reviewed extractor version 2 contract")
    normalized = normalize_profile(**{key: profile[key] for key in PROFILE_FIELDS})
    owned = set(normalized["owned_skills"])
    result: JobComparison = {
        "profile_revision": profile["revision"], "extractor_version": extraction["extractor_version"],
        "source": extraction["source"], "posting_id": extraction["posting_id"],
        "detail_fetched_at": extraction["detail_fetched_at"], "quality_status": extraction["quality_status"],
        "required": [], "preferred": [], "responsibilities": [], "groups": [], "review": [],
        "conditions": _compare_conditions(normalized, extraction["conditions"]),
        "posting_role": posting_role, "role_alignment": "unknown",
    }
    if posting_role in ROLE_LABELS and posting_role != UNKNOWN:
        result["role_alignment"] = "target_role" if posting_role in normalized["target_roles"] else "outside_target_roles"
    buckets = {"required": ("required", "matched", "profile_missing"),
               "preferred": ("preferred", "matched_preferred", "profile_missing_preferred"),
               "responsibility": ("responsibilities", "profile_has", "profile_not_listed")}
    for skill in extraction["skills"]:
        evidence = skill["evidence"]
        independent = [e for e in evidence if e["relation"] == "independent"]
        if independent:
            kind = independent_requirement_type(independent)
            if kind != "unspecified":
                bucket, present, missing = buckets[kind]
                result[bucket].append({"skill": skill["skill"], "requirement_type": kind,
                                       "status": present if skill["skill"] in owned else missing, "evidence": evidence})
            uncertain = [e for e in independent if e["requirement_type"] == "unspecified"]
            if uncertain:
                result["review"].append({"skill": skill["skill"], "reason": "unclassified_evidence", "evidence": uncertain})
        positive_classes = {e["requirement_type"] for e in evidence if e["requirement_type"] != "unspecified"}
        if len(positive_classes) > 1:
            result["review"].append({"skill": skill["skill"], "reason": "mixed_classifications", "evidence": evidence})
        if positive_classes and any(e["rule"] == "negated" for e in evidence):
            result["review"].append({"skill": skill["skill"], "reason": "positive_and_negated_evidence", "evidence": evidence})
    for group in extraction["groups"]:
        present = [skill for skill in group["skills"] if skill in owned]
        missing = [skill for skill in group["skills"] if skill not in owned]
        kind = group["requirement_type"]
        if kind == "unspecified":
            status = "unknown"
            result["review"].append({"skill": None, "reason": "unclassified_group", "evidence": [group["evidence"]]})
        elif kind == "responsibility":
            status = "context_only"
        elif group["relation"] == "any_of":
            status = "satisfied" if present else "not_satisfied_from_profile"
        elif group["relation"] == "all_of":
            status = "satisfied" if not missing else "partially_satisfied" if present else "not_satisfied_from_profile"
        else:
            raise ValueError("Unsupported requirement group relation")
        result["groups"].append({**group, "profile_has": present, "profile_not_listed": missing, "status": status})
    if extraction["unclassified_evidence"]:
        result["review"].append({"skill": None, "reason": "unmapped_evidence", "evidence": extraction["unclassified_evidence"]})
    # Output mutation must not rewrite extraction evidence or a previously saved profile.
    return deepcopy(result)
