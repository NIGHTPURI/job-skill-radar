"""One-shot profile-driven discovery; no daemon, scheduler or hidden network loop."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from jobskillradar.config import get_work24_auth_key
from jobskillradar.discovery_pipeline import discover_work24_jobs


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError('Invalid discovery arguments')


def main(argv=None, *, collector=None, detail_fetcher=None) -> int:
    parser = SafeArgumentParser(description='저장된 목표 직무로 고용24를 한 번 검색하고 실행을 저장합니다.')
    parser.add_argument('--db-path', type=Path, help='Optional local SQLite path')
    parser.add_argument('--pages', type=int, default=1, help='Pages per query: 1-2')
    parser.add_argument('--display', type=int, default=20, help='Results per page: 1-50')
    parser.add_argument('--max-details', type=int, default=20, help='Detail request budget: 0-50')
    parser.add_argument('--refresh-existing-details', action='store_true')
    parser.add_argument('--json', action='store_true', help='Print safe run metadata as JSON')
    try:
        args = parser.parse_args(argv)
        key = get_work24_auth_key()
        if not key:
            print('WORK24_AUTH_KEY를 설정하세요. 자동 검색에는 저장된 목표 직무도 필요합니다.', file=sys.stderr)
            return 1
        result = discover_work24_jobs(key, db_path=args.db_path, pages=args.pages, display=args.display,
            max_details=args.max_details, refresh_existing_details=args.refresh_existing_details,
            collector=collector, detail_fetcher=detail_fetcher)
    except Exception:
        print('검색 실행 실패: 인수 범위, 저장된 프로필, API 키와 DB 상태를 확인하세요. 기존 데이터는 유지됩니다.', file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(f"검색 {result['status']} · 실행 {result['run_id']} · 프로필 버전 {result['profile_revision']}")
        print('검색어: ' + ', '.join(q['keyword'] for q in result['plan']['queries']))
        print(f"공고 {len(result['postings'])} · 로컬 신규 {result['new_postings']} · 기존 {len(result['postings']) - result['new_postings']}")
        print(f"상세 성공 {result['details_saved']} · 재사용 {result['details_reused']} · 예산 미수집 {result['details_deferred']} · 실패 {len(result['detail_failures'])}")
        print(f"검색어 실패 {len(result['query_failures'])}. 새 공고는 이 로컬 DB에 처음 발견됐다는 뜻입니다.")
    return {'completed': 0, 'partial': 2, 'failed': 1}[result['status']]


if __name__ == '__main__':
    raise SystemExit(main())
