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
from jobskillradar.pipeline import analyze_sample, collect_work24_to_db, load_db_analysis, seed_sample_db
from jobskillradar.recommender import recommend_skills


st.set_page_config(page_title="Job Skill Radar", layout="wide")


def counter_frame(counter: Counter, name_col: str, value_col: str, limit: int | None = None) -> pd.DataFrame:
    rows = counter.most_common(limit)
    return pd.DataFrame(rows, columns=[name_col, value_col])


@st.cache_data(ttl=60)
def load_analysis(mode: str) -> tuple[dict, str]:
    if mode == "DB 우선":
        db_analysis = load_db_analysis()
        if db_analysis:
            return db_analysis, "DB"
    return analyze_sample(), "샘플"


st.title("Job Skill Radar")

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

analysis, source_label = load_analysis(data_mode)
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
target_role = st.selectbox("목표 직무", ROLE_LABELS)
owned_raw = st.text_input("보유 기술", value="SQL", placeholder="예: SQL, Python, Tableau")
owned_skills = [skill.strip() for skill in owned_raw.split(",") if skill.strip()]

recommendations = recommend_skills(target_role, owned_skills, analysis, limit=6)
rec_cols = st.columns(3)
for index, item in enumerate(recommendations):
    with rec_cols[index % 3]:
        st.metric(item["skill"], f"점수 {item['score']}")
        st.caption(item["reason"])

st.subheader("공고 목록")
posting_df = pd.DataFrame(postings)
posting_df["skills"] = posting_df["skills"].apply(lambda values: ", ".join(values))
st.dataframe(
    posting_df[["company", "title", "role", "region", "career", "skills", "closing_at"]],
    width="stretch",
    hide_index=True,
)
