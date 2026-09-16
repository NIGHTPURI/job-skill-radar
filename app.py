from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from jobskillradar.analyzer import ROLE_LABELS
from jobskillradar.config import get_db_path, get_work24_auth_key
from jobskillradar.models import AnalysisResult
from jobskillradar.pipeline import collect_work24_to_db, load_market_analysis as select_analysis, seed_sample_db
from jobskillradar.review_ui import render_manual_create, render_posting_browser
from jobskillradar.profile_ui import render_profile
from jobskillradar.pipeline import load_profile
from jobskillradar.recommender import recommend_skills
from jobskillradar.role_classifier import UNKNOWN


st.set_page_config(page_title="Job Skill Radar", layout="wide")


def counter_frame(counter: Counter, name_col: str, value_col: str, limit: int | None = None) -> pd.DataFrame:
    rows = counter.most_common(limit)
    return pd.DataFrame(rows, columns=[name_col, value_col])


@st.cache_data(ttl=60)
def load_analysis(mode: str, db_path: Path) -> tuple[AnalysisResult, str]:
    return select_analysis(mode, db_path=db_path)


st.title("Job Skill Radar")

if next_navigation := st.session_state.pop("next_navigation", None):
    st.session_state["navigation"] = next_navigation
navigation = st.sidebar.radio("화면", ["공고 목록", "공고 직접 등록", "내 프로필", "시장 분석"], key="navigation")
if navigation == "내 프로필":
    render_profile()
    st.stop()
if navigation == "공고 직접 등록":
    render_manual_create()
    st.stop()
if navigation == "공고 목록":
    render_posting_browser()
    st.stop()
st.caption("시장 분석은 저장된 고용24 공고만 사용합니다. 데이터가 없으면 샘플로 표시합니다. 직접 등록한 공고는 제외됩니다.")

with st.sidebar:
    st.header("데이터")
    data_mode = st.radio("불러오기 방식", ["DB 우선", "샘플"], horizontal=True)
    st.caption(f"DB 경로: {get_db_path()}")

    if st.button("샘플 데이터 DB 저장", width="stretch"):
        saved = seed_sample_db()
        st.cache_data.clear()
        st.success(f"샘플 데이터 저장 완료: 신규 {saved}건")

    st.divider()
    st.header("실제 공고 수집")
    api_key = get_work24_auth_key()
    st.caption("고용24 API 키 상태: " + ("설정됨" if api_key else "미설정"))
    keyword_text = st.text_input("검색 키워드", value="데이터 분석가, 데이터 엔지니어, 머신러닝")
    pages = st.number_input("키워드별 페이지 수", min_value=1, max_value=5, value=1, step=1)

    collect_clicked = st.button(
        "고용24에서 수집",
        disabled=not bool(api_key),
        width="stretch",
    )
    if collect_clicked:
        keywords = [keyword.strip() for keyword in keyword_text.split(",") if keyword.strip()]
        with st.spinner("채용공고를 수집하고 DB에 저장하는 중입니다."):
            saved = collect_work24_to_db(api_key, keywords=keywords, pages=int(pages))
        st.cache_data.clear()
        st.success(f"수집 완료: 신규 {saved}건")

    if not api_key:
        st.info(".env 파일에 WORK24_AUTH_KEY를 넣으면 실제 공고 수집 버튼이 활성화됩니다.")

analysis, source_label = load_analysis(data_mode, get_db_path())
postings = analysis["postings"]

metric_cols = st.columns(5)
metric_cols[0].metric("데이터", source_label)
metric_cols[1].metric("공고", f"{len(postings):,}")
metric_cols[2].metric("직무", f"{len(analysis['role_counts']):,}")
metric_cols[3].metric("기술", f"{len(analysis['skill_counts']):,}")
metric_cols[4].metric("지역", f"{len(analysis['region_counts']):,}")

left, right = st.columns([1, 1])

with left:
    skill_df = counter_frame(analysis["skill_counts"], "skill", "count", limit=12)
    st.subheader("기술스택 TOP 12")
    st.plotly_chart(
        px.bar(
            skill_df.sort_values("count"),
            x="count",
            y="skill",
            orientation="h",
            color="count",
            color_continuous_scale="Teal",
        ),
        width="stretch",
    )

with right:
    role_df = counter_frame(analysis["role_counts"], "role", "count")
    st.subheader("직무 분포")
    st.plotly_chart(
        px.pie(role_df, names="role", values="count", color_discrete_sequence=px.colors.qualitative.Set2),
        width="stretch",
    )

career_col, region_col = st.columns([1, 1])

with career_col:
    career_df = counter_frame(analysis["career_counts"], "career", "count")
    st.subheader("경력 조건")
    st.plotly_chart(px.bar(career_df, x="career", y="count", color="career"), width="stretch")

with region_col:
    region_df = counter_frame(analysis["region_counts"], "region", "count")
    st.subheader("지역")
    st.plotly_chart(px.bar(region_df, x="region", y="count", color="region"), width="stretch")

st.subheader("학습 우선순위")
st.caption("현재 분석한 공고의 기술 언급과 역할 기초 지식에 따른 학습 후보입니다. 합격 확률이나 공고별 적합도가 아닙니다.")
profile = load_profile()
profile_revision = profile["revision"] if profile else 0
default_role = profile["target_roles"][0] if profile else ROLE_LABELS[0]
target_role = st.selectbox("목표 직무", ROLE_LABELS, index=ROLE_LABELS.index(default_role), key=f"market_role_{profile_revision}")
owned_raw = st.text_input("보유 기술", value=", ".join(profile["owned_skills"]) if profile else "SQL",
                          placeholder="예: SQL, Python, Tableau", key=f"market_skills_{profile_revision}")
st.caption("저장 프로필을 기본값으로 사용합니다. 이 화면의 임시 변경은 프로필에 저장하지 않습니다.")
owned_skills = [skill.strip() for skill in owned_raw.split(",") if skill.strip()]

recommendations = recommend_skills(target_role, owned_skills, analysis, limit=6)
if target_role == UNKNOWN:
    st.info("미분류 / 기타는 목표 직무가 아니므로 학습 추천을 제공하지 않습니다. 구체적인 목표 직무를 선택하세요.")
else:
    if not analysis["role_counts"].get(target_role, 0):
        st.info("현재 데이터에 목표 직무 공고가 없어 기초 학습 후보만 표시합니다.")
    elif not analysis["role_skill_counts"].get(target_role):
        st.info("목표 직무 공고에서 기술 언급이 추출되지 않아 기초 학습 후보만 표시합니다.")
    if not recommendations:
        st.info("현재 추천 후보에서 보유 기술을 제외하면 남는 기술이 없습니다.")
rec_cols = st.columns(3)
for index, item in enumerate(recommendations):
    with rec_cols[index % 3]:
        st.metric(item["skill"], f"{item['priority']}순위")
        st.caption(item["reason"])

st.subheader("공고 목록")
posting_df = pd.DataFrame(postings)
posting_df["skills"] = posting_df["skills"].apply(lambda values: ", ".join(values))
st.dataframe(
    posting_df[["company", "title", "role", "region", "career", "skills", "closing_at"]],
    width="stretch",
    hide_index=True,
)
