"""Pure bounded role-driven Work24 planning; owned skills never filter discovery."""
from __future__ import annotations

from .models import DiscoveryPlan
from .profile import TARGET_ROLES
from .role_classifier import (BACKEND, BI_ANALYST, DATA_ANALYST, DATA_ENGINEER,
                              DEVOPS, FRONTEND, FULL_STACK, ML_ENGINEER)

ROLE_QUERIES = {
    DATA_ANALYST: ("데이터 분석", "data analyst"),
    DATA_ENGINEER: ("데이터 엔지니어", "데이터 파이프라인"),
    ML_ENGINEER: ("머신러닝", "AI 엔지니어"),
    BI_ANALYST: ("BI 개발", "BI 분석"),
    BACKEND: ("백엔드", "서버 개발"),
    FRONTEND: ("프론트엔드", "frontend"),
    FULL_STACK: ("풀스택", "fullstack"),
    DEVOPS: ("DevOps", "클라우드 엔지니어"),
}
MAX_QUERIES = 16
DEFAULT_PAGES, MAX_PAGES = 1, 2
DEFAULT_DISPLAY, MAX_DISPLAY = 20, 50
DEFAULT_MAX_DETAILS, MAX_DETAILS = 20, 50


def build_discovery_plan(profile: dict | None) -> DiscoveryPlan:
    roles = [] if profile is None else profile.get("target_roles", [])
    if not isinstance(roles, list) or any(role not in TARGET_ROLES for role in roles):
        raise ValueError("Discovery requires supported target roles")
    selected = [role for role in TARGET_ROLES if role in roles]
    queries = []
    for role in selected:
        for term in ROLE_QUERIES[role]:
            existing = next((q for q in queries if q["keyword"] == term), None)
            if existing is None:
                queries.append({"keyword": term, "target_roles": [role]})
            elif role not in existing["target_roles"]:
                existing["target_roles"].append(role)
    if len(queries) > MAX_QUERIES:
        raise ValueError("Discovery query cap exceeded")
    return {"status": "ready" if selected else "profile_needs_target_role",
            "target_roles": selected, "queries": queries}


def validate_budget(pages: int, display: int, max_details: int) -> None:
    for name, value, minimum, maximum in (("pages", pages, 1, MAX_PAGES),
                                          ("display", display, 1, MAX_DISPLAY),
                                          ("max_details", max_details, 0, MAX_DETAILS)):
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError(f"{name} must be an integer between {minimum} and {maximum}")
