"""Intentional one-shot discovery actions and offline review of persisted runs."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from .config import get_db_path, get_work24_auth_key
from .discovery import build_discovery_plan
from .discovery_pipeline import discover_work24_jobs, load_discovery_shortlist
from .discovery_storage import list_discovery_runs
from .pipeline import load_profile
from .shortlist import BUCKET_ORDER

BUCKET_LABELS = {'review_first': '먼저 검토', 'review_with_gaps': '필수 요건 확인 필요',
                 'needs_information': '정보 부족', 'outside_current_target': '현재 목표/조건 밖'}
STATUS_LABELS = {'completed': '완료', 'partial': '부분 완료', 'failed': '검색 실패'}
REASON_LABELS = {
    'found_by_queries': '발견한 검색어', 'new_to_local_database': '이 실행에서 로컬 DB에 처음 발견',
    'known_to_local_database': '이미 로컬 DB에 있던 공고', 'target_role_aligned': '목표 직무에 포함',
    'outside_target_roles': '현재 목표 직무와 다름', 'role_unknown': '직무를 확정하지 못함',
    'hard_condition_mismatch': '원문에서 확인한 필수 조건 불일치',
    'hard_condition_unknown': '필수 조건을 판단할 정보 부족',
    'condition_preference_mismatch': '선호 조건과 다름 (필수 위반 아님)',
    'required_not_listed': '필수 기술이 저장 프로필에 미등록',
    'required_any_of_not_represented': '필수 선택 조건 중 프로필에 등록된 구성원이 없음',
    'required_all_of_not_represented': '필수 공동 조건의 일부 또는 전부가 프로필에 미등록',
    'preferred_not_listed': '우대 기술이 프로필에 미등록 (필수 부족 아님)',
    'preferred_any_of_not_represented': '우대 선택 조건을 프로필에서 확인하지 못함',
    'preferred_all_of_not_represented': '우대 공동 조건을 프로필에서 전부 확인하지 못함',
    'detail_not_fetched': '상세 원문이 아직 없음',
    'detail_fetched_but_no_requirement_evidence': '현재 규칙으로 요건 근거를 찾지 못함',
    'requirement_evidence_present_but_unclassified': '요건 근거가 있으나 분류하지 못함',
    'evidence_needs_review': '미분류 또는 충돌 근거를 직접 확인해야 함',
    'no_classified_qualification_evidence': '업무 근거만 있어 자격 요건 판단이 어려움',
    'no_detected_required_profile_gaps': '현재 근거에서 필수 프로필 미등록이 검출되지 않음 — 자격 충족 판정 아님',
}
VALUE_LABELS = {'work_region': '지역', 'unclassified_evidence': '미분류 근거',
                'mixed_classifications': '서로 다른 분류', 'positive_and_negated_evidence': '긍정·부정 공존',
                'unclassified_group': '그룹 의미 미확정', 'unmapped_evidence': '기술로 연결하지 못한 근거'}


def _time_label(value: str) -> str:
    return datetime.fromisoformat(value).astimezone(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S KST')


def _render_summary(run: dict, current_revision: int) -> None:
    st.subheader('검색 실행 요약')
    st.text(f"{STATUS_LABELS[run['status']]} · {_time_label(run['completed_at'])}")
    st.caption(f"검색 당시 프로필 버전 {run['profile_revision']} · 현재 비교 버전 {current_revision}")
    st.text('검색 당시 목표: ' + ', '.join(run['plan']['target_roles']))
    st.text('사용한 검색어: ' + ', '.join(q['keyword'] for q in run['plan']['queries']))
    cols = st.columns(4)
    for column, label, value in zip(cols, ('발견 공고', '새로 발견', '이미 알고 있던 공고', '상세 수집 성공'),
                                    (len(run['postings']), run['new_postings'], len(run['postings']) - run['new_postings'], run['details_saved'])):
        column.metric(label, value)
    st.caption(f"상세 재사용 {run['details_reused']} · 예산 미수집 {run['details_deferred']} · "
               f"상세 실패 {len(run['detail_failures'])} · 검색어 실패 {len(run['query_failures'])}")
    if run['status'] == 'partial':
        st.warning('부분 완료: 성공한 공고는 저장했습니다. 실패한 요청과 정보 부족 공고를 확인하세요.')
    elif run['status'] == 'failed':
        st.error('모든 검색어 요청이 실패했습니다. 이전 검색은 아래 실행 선택에서 다시 볼 수 있습니다.')
    if run['detail_failures'] or run['query_failures']:
        with st.expander('요청 실패 내역'):
            for failure in run['query_failures']:
                st.text(f"검색어 {failure['query']}: {failure['reason']}")
            for failure in run['detail_failures']:
                st.text(f"상세 {failure['posting_id']}: {failure['reason']} (기존 성공 원문은 보존)")
    if run['details_deferred']:
        st.info('요청 예산 때문에 일부 상세를 가져오지 않았습니다. 다음 검색에서 상세 없는 공고를 다시 시도합니다.')


def _render_items(items: list[dict], run_id: str) -> None:
    st.caption('먼저 검토는 현재 근거상 필수 미등록 미검출을 뜻합니다. 적합도·합격 가능성 판정이 아닙니다. 마감 여부는 원문에서 확인하세요.')
    labels = ['전체'] + [BUCKET_LABELS[bucket] for bucket in BUCKET_ORDER]
    selected = st.selectbox('검토 분류', labels, key='discovery_bucket')
    only_new = st.checkbox('새로 발견한 공고만', key='discovery_only_new')
    filtered = [i for i in items if (selected == '전체' or BUCKET_LABELS[i['bucket']] == selected)
                and (not only_new or i['membership']['was_new'])]
    st.text(f'표시할 공고 {len(filtered)}건')
    if not filtered:
        st.info('이 필터에 해당하는 공고가 없습니다. 다른 분류나 이전 검색을 확인하세요.')
        return
    pages = max(1, (len(filtered) + 19) // 20)
    page = st.selectbox('결과 페이지', list(range(1, pages + 1)), key=f'discovery_page_{run_id}_{selected}_{only_new}')
    for item in filtered[(page - 1) * 20:page * 20]:
        posting, member = item['posting'], item['membership']
        with st.container(border=True):
            st.subheader((posting.get('company') or '회사 미상') + ' · ' + (posting.get('title') or '제목 미상'))
            st.text(f"{'새로 발견' if member['was_new'] else '기존 공고'} · {BUCKET_LABELS[item['bucket']]} · {posting['role']}")
            st.caption(f"지역: {posting.get('region') or '미상'} · 마감: {posting.get('closing_at') or '미상'}")
            for reason in item['reasons']:
                values = [VALUE_LABELS.get(v, v) for v in reason['values']]
                joiner = ' 또는 ' if 'any_of' in reason['code'] else ' 그리고 ' if 'all_of' in reason['code'] else ', '
                st.text(REASON_LABELS[reason['code']] + (': ' + joiner.join(values) if values else ''))
            url = posting.get('url') or ''
            if url.startswith(('https://', 'http://')):
                st.link_button('원문 사이트', url)
            if st.button('공고 열기', key='discovery_open_' + member['posting_id']):
                st.session_state['open_posting'] = (member['source'], member['posting_id'])
                st.session_state['next_navigation'] = '공고 목록'
                st.rerun()


def render_discovery() -> None:
    st.header('새 공고 찾기')
    st.caption('저장한 목표 직무로 고용24를 검색합니다. 보유 기술로 검색 범위를 좁히지 않습니다.')
    st.caption('‘새 공고’는 이 로컬 앱이 해당 실행에서 처음 발견했다는 뜻이며, 오늘 게시된 공고라는 뜻은 아닙니다.')
    try:
        profile = load_profile()
        plan = build_discovery_plan(profile)
        if plan['status'] != 'ready':
            st.info('자동 검색에는 목표 직무가 필요합니다. 왼쪽 ‘내 프로필’에서 목표 직무를 선택하고 저장하세요.')
            return
        st.text('현재 목표 직무: ' + ', '.join(plan['target_roles']))
        st.text('자동 검색어: ' + ', '.join(q['keyword'] for q in plan['queries']))
        key = get_work24_auth_key()
        if not key:
            st.info('고용24 검색을 사용하려면 .env의 WORK24_AUTH_KEY를 설정하세요. 키 없이도 공고 직접 등록과 저장된 검색 검토를 사용할 수 있습니다.')
        with st.expander('상세 갱신 옵션'):
            refresh = st.checkbox('기존 성공 상세도 다시 가져오기', key='discovery_refresh')
            st.caption('기본은 기존 성공 상세 재사용입니다. 다시 가져오기도 실행당 최대 20회 안에서 처리하며 새 공고와 상세 없는 공고가 우선입니다.')
        st.caption(f"기본 검색: 목록 최대 {len(plan['queries'])}회 (검색어당 20건), 상세 최대 20회. 버튼을 눌러야 외부 요청을 보냅니다.")
        if st.button('새 공고 찾기', disabled=not bool(key), key='discover_jobs', type='primary'):
            progress = st.empty()
            def update(stage, current, total):
                progress.info(f"{'공고 검색' if stage == 'query' else '상세 수집'} {current}/{total} 진행 중")
            try:
                run = discover_work24_jobs(key, refresh_existing_details=refresh, progress=update)
            except Exception:
                # Never render arbitrary network/database exception strings or tracebacks.
                st.error('검색 실행을 저장하지 못했습니다. 설정과 DB 상태를 확인하세요. 이전 검색 기록은 유지됩니다.')
            else:
                st.session_state['discovery_run'] = run['run_id']
                st.cache_data.clear()
            finally:
                progress.empty()
        history = list_discovery_runs(get_db_path())
        if not history:
            st.info('저장된 검색 실행이 없습니다. 위 버튼으로 첫 검색을 실행하세요.')
            return
        by_id = {r['run_id']: r for r in history}
        if st.session_state.get('discovery_run') not in by_id:
            st.session_state['discovery_run'] = history[0]['run_id']
        run_id = st.selectbox('검색 실행 선택 (최근 20회)', list(by_id), key='discovery_run',
                             format_func=lambda rid: f"{_time_label(by_id[rid]['completed_at'])} · {STATUS_LABELS[by_id[rid]['status']]} · {rid[:8]}")
        view = load_discovery_shortlist(run_id=run_id)
        _render_summary(view['run'], view['profile_revision'])
        _render_items(view['items'], run_id)
    except Exception:
        st.error('저장된 검색이나 프로필을 읽지 못했습니다. DB 상태와 설정을 확인하세요. 외부 요청 오류의 원문은 표시하지 않습니다.')
