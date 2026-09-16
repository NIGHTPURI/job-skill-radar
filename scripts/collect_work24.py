from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jobskillradar.config import get_db_path, get_work24_auth_key
from jobskillradar.pipeline import DEFAULT_KEYWORDS, collect_work24_to_db, collect_work24_with_details_to_db
from jobskillradar.work24_client import Work24Error


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="고용24 채용공고 수집")
    parser.add_argument(
        "--keyword",
        action="append",
        help="검색 키워드입니다. 여러 번 입력할 수 있습니다.",
    )
    parser.add_argument("--pages", type=int, default=1, help="키워드별 수집 페이지 수")
    parser.add_argument("--display", type=int, default=100, help="페이지당 공고 수")
    parser.add_argument(
        "--with-details", action="store_true",
        help="Fetch or refresh official detail evidence once per collected posting.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    auth_key = get_work24_auth_key()
    if not auth_key:
        print("WORK24_AUTH_KEY 환경변수가 없습니다. .env.example을 참고해 인증키를 설정하세요.")
        raise SystemExit(1)

    keywords = args.keyword or DEFAULT_KEYWORDS
    collect = collect_work24_with_details_to_db if args.with_details else collect_work24_to_db
    try:
        result = collect(
            auth_key=auth_key,
            keywords=keywords,
            pages=args.pages,
            display=args.display,
        )
    except Work24Error as error:
        print(f"Collection failed: {error.kind}")
        raise SystemExit(1) from None

    print(f"검색 키워드: {', '.join(keywords)}")
    saved = result["new_postings"] if args.with_details else result
    print(f"신규 저장: {saved}건")
    if args.with_details:
        print(f"Details saved: {result['details_saved']}; failed: {len(result['detail_failures'])}")
        for failure in result["detail_failures"]:
            print(f"Detail failed: {failure['source']}/{failure['posting_id']} ({failure['reason']})")
    print(f"DB 경로: {get_db_path()}")
    if args.with_details and result["detail_failures"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
