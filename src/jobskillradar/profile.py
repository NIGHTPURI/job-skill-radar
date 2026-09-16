"""One local profile: canonical skills, role intent and explicit region choices."""
from __future__ import annotations

from .models import ProfileValues
from .normalizer import REGION_ALIASES
from .role_classifier import ROLE_LABELS, UNKNOWN
from .skill_extractor import canonicalize_skills

PROFILE_FIELDS = ("owned_skills", "target_roles", "preferred_regions", "required_regions")
TARGET_ROLES = tuple(role for role in ROLE_LABELS if role != UNKNOWN)
REGIONS = tuple(REGION_ALIASES)


def normalize_profile(*, owned_skills: list[str], target_roles: list[str],
                      preferred_regions: list[str] | None = None,
                      required_regions: list[str] | None = None) -> ProfileValues:
    """Canonicalize known aliases; retain unknown skill spelling explicitly.

    Lists are semantic sets. Reordering, duplicates and known alias spelling do
    not change a profile revision. Empty region lists impose no declared choice.
    No geographic inference, experience years or implicit hard preferences.
    """
    values = {"owned_skills": owned_skills, "target_roles": target_roles,
              "preferred_regions": [] if preferred_regions is None else preferred_regions,
              "required_regions": [] if required_regions is None else required_regions}
    for field, items in values.items():
        if not isinstance(items, list) or any(not isinstance(item, str) for item in items):
            raise ValueError(f"{field} must be a list of strings")
        values[field] = sorted({item.strip() for item in items if item.strip()}, key=lambda item: (item.casefold(), item))
    values["owned_skills"] = sorted(set(canonicalize_skills(values["owned_skills"])), key=lambda item: (item.casefold(), item))
    if not values["target_roles"] or not set(values["target_roles"]) <= set(TARGET_ROLES):
        raise ValueError("Select at least one supported target role")
    for field in ("preferred_regions", "required_regions"):
        if not set(values[field]) <= set(REGIONS):
            raise ValueError(f"{field} must contain supported exact region labels")
    return values
