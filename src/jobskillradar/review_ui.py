"""Small Streamlit views; persistence and extraction stay behind application APIs."""
from __future__ import annotations

import sqlite3

import streamlit as st

from .matcher import independent_requirement_type
from .pipeline import create_manual_posting, list_saved_postings, load_posting_comparison, load_posting_review, update_manual_posting

KIND_LABELS = {"required": "필수 요건", "preferred": "우대 요건",
               "responsibility": "업무 관련 기술", "unspecified": "판단 필요"}
QUALITY_LABELS = {
    "detail_not_fetched": "상세 원문이 아직 저장되지 않았습니다.",
    "detail_fetched_but_no_requirement_evidence": "현재 규칙으로 요건 근거를 찾지 못했습니다. 요건이 없다는 뜻은 아닙니다.",
    "requirements_extracted": "분류된 요건 근거가 있습니다. 원문과 미분류 근거도 확인하세요.",
    "requirement_evidence_present_but_unclassified": "근거는 있으나 확정적으로 분류하지 못했습니다. 직접 검토가 필요합니다.",
}


def render_requirements(extraction: dict) -> None:
    st.info(QUALITY_LABELS[extraction["quality_status"]])
    st.caption(f"추출 규칙 버전 {extraction['extractor_version']} · 원문에서 다시 계산한 결과")
    for kind, label in KIND_LABELS.items():
        with st.expander(label, expanded=kind in {"required", "preferred"}):
            items = [s for s in extraction["skills"] if independent_requirement_type(s["evidence"]) == kind]
            if not items:
                st.caption("이 범주로 분류된 개별 기술 근거가 없습니다. 선택 조건과 원문도 확인하세요.")
            for item in items:
                st.write(item["skill"])
                st.json(item["evidence"], expanded=False)
    st.subheader("선택 조건 / 공동 조건")
    for group in extraction["groups"]:
        joiner = " 또는 " if group["relation"] == "any_of" else " 그리고 "
        meaning = "하나 이상" if group["relation"] == "any_of" else "모두"
        st.write(f"{KIND_LABELS[group['requirement_type']]}: {joiner.join(group['skills'])} — {meaning}")
        st.json(group["evidence"], expanded=False)
    if extraction["unclassified_evidence"]:
        with st.expander("기술로 연결하지 못한 근거"):
            st.json(extraction["unclassified_evidence"])
    with st.expander("기타 조건 원문"):
        st.json(extraction["conditions"])


def _manual_form(key: str, review: dict | None = None) -> dict | None:
    posting = review["posting"] if review else {}
    detail = (review["detail"] or {}) if review else {}
    with st.form(key):
        company = st.text_input("회사명 *", value=posting.get("company") or "", key=key + "_company")
        title = st.text_input("공고 제목 *", value=posting.get("title") or "", key=key + "_title")
        body = st.text_area("공고 본문 *", value=detail.get("job_content") or "", height=280, key=key + "_body")
        url = st.text_input("원문 URL (선택)", value=posting.get("url") or "", key=key + "_url")
        region = st.text_input("근무 지역 원문 (선택)", value=detail.get("work_region") or "", key=key + "_region")
        career = st.text_input("경력 조건 원문 (선택)", value=detail.get("raw_career_condition") or "", key=key + "_career")
        education = st.text_input("학력 원문 (선택)", value=detail.get("education") or "", key=key + "_education")
        closing_at = st.text_input("마감일 원문 (선택)", value=posting.get("closing_at") or "", key=key + "_closing")
        submitted = st.form_submit_button("수정 저장" if review else "공고 등록")
    if submitted:
        if not all(value.strip() for value in (company, title, body)):
            st.error("회사명, 공고 제목, 본문을 모두 입력하세요. 입력 내용은 유지됩니다.")
            return None
        return dict(company=company, title=title, body=body, url=url, region=region, career=career,
                    education=education, closing_at=closing_at)
    return None


def render_manual_create() -> None:
    st.header("공고 직접 등록")
    st.caption("직접 복사한 공고를 보관합니다. 외부 사이트에 접속하거나 수집하지 않습니다. 시장 집계에는 포함되지 않습니다.")
    values = _manual_form("manual_create")
    if values:
        try:
            posting_id = create_manual_posting(**values)
        except ValueError as error:
            st.error(f"입력을 확인하세요: {error}")
        except (sqlite3.Error, OSError):
            st.error("저장하지 못했습니다. DB 경로와 파일 권한을 확인하세요. 입력 내용은 유지됩니다.")
        else:
            st.session_state["open_posting"] = ("manual", posting_id)
            st.session_state["next_navigation"] = "공고 목록"
            st.session_state["posting_notice"] = "공고를 등록했습니다."
            st.rerun()


def render_posting_browser() -> None:
    st.header("저장한 공고")
    if notice := st.session_state.pop("posting_notice", None):
        st.success(notice)
    try:
        postings = list_saved_postings()
        if not postings:
            st.info("저장한 공고가 없습니다. 왼쪽의 ‘공고 직접 등록’에서 첫 공고를 등록하세요.")
            return
        by_identity = {(p["source"], p["posting_id"]): p for p in postings}
        options = list(by_identity)
        requested = st.session_state.pop("open_posting", None)
        if requested in by_identity:
            st.session_state["selected_posting"] = requested
        if st.session_state.get("selected_posting") not in by_identity:
            st.session_state["selected_posting"] = options[0]
        identity = st.selectbox("공고 선택", options, key="selected_posting",
                                format_func=lambda key: f"[{key[0]}] {by_identity[key]['company']} · {by_identity[key]['title']} · {key[1][:8]}")
        review = load_posting_review(*identity)
    except (ValueError, sqlite3.Error, OSError):
        st.error("공고를 불러오지 못했습니다. DB 상태를 확인하고 다시 시도하세요.")
        return
    posting, detail = review["posting"], review["detail"]
    st.subheader(posting["title"] or "제목 미상")
    st.text(f"{posting['company']} · 출처: {posting['source']} · ID: {posting['posting_id']}")
    url = posting.get("url") or ""
    if url.startswith(("http://", "https://")):
        st.link_button("원문 열기", url)
    with st.expander("저장한 원문", expanded=True):
        st.text((detail or {}).get("job_content") or "상세 본문이 없습니다.")
        if detail:
            st.caption("원문 저장/관측 시각: " + detail["fetched_at"])
    render_requirements(review["requirements"])
    if st.checkbox("내 프로필과 비교", key="compare_" + identity[0] + "_" + identity[1]):
        render_comparison(*identity)
    if identity[0] == "manual":
        with st.expander("수동 공고 수정"):
            key = "manual_edit_" + identity[1] + "_" + ((detail or {}).get("fetched_at") or "missing")
            values = _manual_form(key, review)
            if values:
                try:
                    update_manual_posting(*identity, **values)
                except ValueError as error:
                    st.error(f"입력을 확인하세요: {error}")
                except (sqlite3.Error, OSError):
                    st.error("수정 내용을 저장하지 못했습니다. 입력 내용은 유지됩니다.")
                else:
                    st.session_state["posting_notice"] = "같은 공고의 원문과 정보를 수정했습니다."
                    st.rerun()


def render_comparison(source: str, posting_id: str) -> None:
    try:
        result = load_posting_comparison(source, posting_id)
    except ValueError as error:
        st.info(f"비교하려면 먼저 ‘내 프로필’에서 프로필을 저장하고 공고 근거를 확인하세요. {error}")
        return
    except (sqlite3.Error, OSError):
        st.error("비교 자료를 읽지 못했습니다. DB 상태를 확인하세요.")
        return
    st.header("내 프로필과 공고 근거 비교")
    st.caption(f"프로필 버전 {result['profile_revision']} · 추출 규칙 버전 {result['extractor_version']}. "
               "프로필에 등록한 내용만 비교합니다. 미등록은 실제 지식 부족의 증명이 아니며, 보유 수준·합격 가능성을 판정하지 않습니다.")
    st.info(QUALITY_LABELS[result["quality_status"]])
    role_labels = {"target_role": "저장한 목표 직무에 포함", "outside_target_roles": "저장한 목표 직무와 다름",
                   "unknown": "직무 분류 판단 필요"}
    st.text(f"공고 직무: {result['posting_role'] or '미상'} · {role_labels[result['role_alignment']]}")
    statuses = {"matched": "프로필에 등록됨", "profile_missing": "프로필에 등록되어 있지 않음",
                "matched_preferred": "우대 기술이 프로필에 등록됨", "profile_missing_preferred": "우대 기술이 프로필에 미등록 (필수 부족 아님)",
                "profile_has": "업무 관련 기술이 프로필에 등록됨", "profile_not_listed": "업무 관련 기술이 프로필에 미등록 (필수 부족 아님)"}
    for bucket, label in (("required", "필수 요건 비교"), ("preferred", "우대 요건 비교"), ("responsibilities", "업무 관련 기술 비교")):
        st.subheader(label)
        if not result[bucket]:
            st.caption("독립적으로 비교할 분류 근거가 없습니다. 조건 충족이나 요건 부재를 뜻하지 않습니다. 아래 그룹과 판단 필요 근거를 확인하세요.")
        for item in result[bucket]:
            st.text(f"{item['skill']}: {statuses[item['status']]}")
            with st.expander("근거 · " + item["skill"]):
                st.json(item["evidence"])
    st.subheader("선택 조건 / 공동 조건 비교")
    group_status = {"satisfied": "프로필 등록 기준 충족", "partially_satisfied": "일부 구성원만 프로필에 등록됨",
                    "not_satisfied_from_profile": "현재 프로필 등록만으로 충족을 확인할 수 없음",
                    "unknown": "요건 의미가 불명확하여 판단 필요", "context_only": "업무 문맥이며 필수 요건 아님"}
    for group in result["groups"]:
        joiner = " 또는 " if group["relation"] == "any_of" else " 그리고 "
        meaning = "하나 이상" if group["relation"] == "any_of" else "모두"
        st.text(f"{KIND_LABELS[group['requirement_type']]}: {joiner.join(group['skills'])} ({meaning}) — {group_status[group['status']]}")
        st.caption("프로필 등록 구성원: " + (", ".join(group["profile_has"]) or "없음") +
                   " / 미등록 구성원: " + (", ".join(group["profile_not_listed"]) or "없음"))
        if group["requirement_type"] == "preferred":
            st.caption("우대 조건이며 필수 부족으로 취급하지 않습니다.")
        with st.expander("그룹 원문 근거 · " + joiner.join(group["skills"])):
            st.json(group["evidence"])
    st.subheader("판단 필요 근거")
    reasons = {"unclassified_evidence": "분류하지 못한 근거", "mixed_classifications": "서로 다른 분류의 근거",
               "positive_and_negated_evidence": "긍정·부정 근거가 함께 있음", "unclassified_group": "그룹 의미 미확정",
               "unmapped_evidence": "기술로 연결하지 못한 원문"}
    for item in result["review"]:
        with st.expander(f"{item['skill'] or '원문'} · {reasons[item['reason']]}"):
            st.json(item["evidence"])
    st.subheader("기타 조건 비교")
    condition_labels = {"raw_career_condition": "경력", "education": "학력", "employment_type": "고용 형태", "work_region": "지역"}
    condition_status = {"satisfied": "저장한 필수 조건과 일치", "not_satisfied": "저장한 필수 조건과 불일치",
                        "preference_match": "선호와 일치", "preference_mismatch": "선호와 불일치 (필수 위반 아님)",
                        "unknown": "판단 불가 — 원문 또는 비교 가능한 프로필 조건 부족"}
    for condition in result["conditions"]:
        st.text(f"{condition_labels[condition['source_field']]}: {condition_status[condition['status']]}")
        st.caption("공고 원문: " + (condition["raw_text"] or "미제공") +
                   " / 프로필 선택: " + (", ".join(condition["expected_values"]) or "설정하지 않음"))
