"""Deterministic metrics for reviewed fixtures, never real-world accuracy.

The unit is (case, canonical skill, effective class). A wrong class counts as
both a false positive for the predicted class and a false negative for the
expected class. Groups are evaluated separately, including relation and members.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable

from .requirement_extractor import extract_requirements
from .skill_taxonomy import SKILL_ALIASES

CLASSES = ("required", "preferred", "responsibility", "unspecified")
QUALITIES = {
    "detail_not_fetched", "detail_fetched_but_no_requirement_evidence",
    "requirements_extracted", "requirement_evidence_present_but_unclassified",
}


def _group_key(group: dict) -> tuple:
    return group["relation"], group["requirement_type"], tuple(sorted(group["skills"]))


def _metrics(tp: int, fp: int, fn: int) -> dict:
    return {
        "true_positives": tp, "false_positives": fp, "false_negatives": fn,
        "fixture_precision": tp / (tp + fp) if tp + fp else None,
        "fixture_recall": tp / (tp + fn) if tp + fn else None,
        "fixture_f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
    }


def validate_cases(cases: list[dict]) -> None:
    """Fail closed on empty, duplicate, or inconsistent manual labels."""
    if not cases:
        raise ValueError("Evaluation corpus must not be empty")
    ids = set()
    for case in cases:
        if not case["id"] or case["id"] in ids or not case["review_note"].strip():
            raise ValueError("Cases require unique IDs and review notes")
        ids.add(case["id"])
        if case["quality"] not in QUALITIES:
            raise ValueError("Unknown quality label")
        for skill, kind in case["expected"].items():
            if skill not in SKILL_ALIASES or kind not in CLASSES:
                raise ValueError("Unknown canonical skill or requirement class")
        for group in case.get("expected_groups", []):
            skills = group["skills"]
            if (group["relation"] not in {"all_of", "any_of"}
                    or group["requirement_type"] not in CLASSES
                    or len(set(skills)) != len(skills) or len(skills) < 2
                    or not set(skills) <= case["expected"].keys()):
                raise ValueError("Invalid expected group")


def evaluate_requirements(cases: list[dict], *, extractor: Callable = extract_requirements) -> dict:
    """Compare frozen manual labels; do not mutate inputs or invoke I/O.

    Gate: every case must match its skill classes, groups and quality. This
    includes zero required/preferred false positives and prevents an all-empty
    extractor from passing. Provenance is checked by separate behavioral tests.
    """
    validate_cases(cases)
    counts = {kind: Counter() for kind in CLASSES}
    group_counts = Counter()
    group_classes = {kind: Counter() for kind in CLASSES}
    mismatches = []
    expected_count = actual_count = exact_matches = classification_mismatches = 0
    versions = set()
    for case in cases:
        result = extractor(case["detail"])
        versions.add(result["extractor_version"])
        expected = set(case["expected"].items())
        actual = [(item["skill"], item["requirement_type"]) for item in result["skills"]]
        # Counters also expose accidental duplicate result rows.
        wanted, found = Counter(expected), Counter(actual)
        tp, fp, fn = wanted & found, found - wanted, wanted - found
        expected_count += wanted.total()
        actual_count += found.total()
        exact_matches += tp.total()
        for name, entries in (("tp", tp), ("fp", fp), ("fn", fn)):
            for (_, kind), count in entries.items():
                counts[kind][name] += count
        actual_map = dict(actual)
        changed = [{"skill": skill, "expected": kind, "actual": actual_map[skill]}
                   for skill, kind in sorted(expected)
                   if skill in actual_map and actual_map[skill] != kind]
        classification_mismatches += len(changed)
        expected_groups = Counter(_group_key(g) for g in case.get("expected_groups", []))
        actual_groups = Counter(_group_key(g) for g in result.get("groups", []))
        group_counts.update(tp=(expected_groups & actual_groups).total(),
                            fp=(actual_groups - expected_groups).total(),
                            fn=(expected_groups - actual_groups).total())
        for name, entries in (("tp", expected_groups & actual_groups),
                              ("fp", actual_groups - expected_groups),
                              ("fn", expected_groups - actual_groups)):
            for (_, kind, _), count in entries.items():
                group_classes[kind][name] += count
        if fp or fn or expected_groups != actual_groups or result["quality_status"] != case["quality"]:
            mismatches.append({
                "id": case["id"], "false_positives": sorted(fp.elements()),
                "false_negatives": sorted(fn.elements()), "classification_mismatches": changed,
                "missing_groups": sorted((expected_groups - actual_groups).elements()),
                "unexpected_groups": sorted((actual_groups - expected_groups).elements()),
                "expected_quality": case["quality"], "actual_quality": result["quality_status"],
            })
    metrics = {kind: _metrics(c["tp"], c["fp"], c["fn"]) for kind, c in counts.items()}
    group_metrics = {kind: _metrics(c["tp"], c["fp"], c["fn"]) for kind, c in group_classes.items()}
    return {
        "scope": "manually reviewed fixtures only; not real-world accuracy",
        "extractor_versions": sorted(versions), "cases": len(cases),
        "exact_cases": len(cases) - len(mismatches), "expected_results": expected_count,
        "actual_results": actual_count, "exact_matches": exact_matches,
        "classification_mismatches": classification_mismatches, "per_class": metrics,
        "required_false_positives": metrics["required"]["false_positives"] + group_metrics["required"]["false_positives"],
        "preferred_false_positives": metrics["preferred"]["false_positives"] + group_metrics["preferred"]["false_positives"],
        "group_per_class": group_metrics,
        "groups": _metrics(group_counts["tp"], group_counts["fp"], group_counts["fn"]),
        "mismatches": mismatches, "passed": not mismatches,
    }
