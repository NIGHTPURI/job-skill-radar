"""Local profile editor; no SQL and no inferred qualification claims."""
from __future__ import annotations

import sqlite3

import streamlit as st

from .pipeline import load_profile, save_profile
from .profile import REGIONS, TARGET_ROLES
from .skill_taxonomy import SKILL_ALIASES


def render_profile() -> None:
    st.header("내 프로필")
    st.caption("이 기기에 한 개의 프로필을 저장합니다. 등록하지 않은 기술이 실제로 모르는 기술이라는 뜻은 아닙니다.")
    try:
        profile = load_profile()
    except (ValueError, sqlite3.Error, OSError):
        st.error("프로필을 읽지 못했습니다. DB 상태를 확인하세요.")
        return
    values = profile or {"owned_skills": [], "target_roles": [], "preferred_regions": [], "required_regions": []}
    revision = profile["revision"] if profile else 0
    if st.session_state.pop("profile_saved", False):
        st.success("프로필을 저장했습니다.")
    st.caption(f"저장 버전: {revision}" if profile else "아직 저장한 프로필이 없습니다.")
    key = f"profile_{revision}"
    with st.form(key):
        skills = st.text_area("보유 기술 (쉼표로 구분)", value=", ".join(values["owned_skills"]), key=key + "_skills")
        roles = st.multiselect("목표 직무 (하나 이상)", TARGET_ROLES, default=values["target_roles"], key=key + "_roles")
        preferred = st.multiselect("선호 지역 (선택)", REGIONS, default=values["preferred_regions"], key=key + "_preferred")
        required = st.multiselect("반드시 충족해야 하는 지역 (선택)", REGIONS, default=values["required_regions"], key=key + "_required")
        st.caption("여러 지역을 선택하면 그중 한 곳입니다. 빈 필수 조건은 지역 제한을 선언하지 않은 상태입니다. "
                   "공고가 단일 시·도 이름으로 명확히 제시한 경우에만 지역을 비교하며, 통근·재택 가능성은 추측하지 않습니다.")
        submitted = st.form_submit_button("프로필 저장")
    if submitted:
        try:
            save_profile(owned_skills=[s.strip() for s in skills.split(",") if s.strip()], target_roles=roles,
                         preferred_regions=preferred, required_regions=required)
        except ValueError as error:
            st.error(f"입력을 확인하세요: {error}")
        except (sqlite3.Error, OSError):
            st.error("프로필을 저장하지 못했습니다. 입력 내용은 유지됩니다.")
        else:
            st.session_state["profile_saved"] = True
            st.rerun()
    unknown = [skill for skill in values["owned_skills"] if skill not in SKILL_ALIASES]
    if unknown:
        st.info("등록은 보존하지만 현재 기술 사전에 없는 항목: " + ", ".join(unknown))
