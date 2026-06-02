from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jobskillradar.config import get_db_path, get_work24_auth_key
from jobskillradar.pipeline import DEFAULT_KEYWORDS, collect_work24_to_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="고용24 채용공고 수집")
    parser.add_argument(
        "--keyword",
        action="append",
        help="검색 키워드입니다. 여러 번 입력할 수 있습니다.",
    )
    parser.add_argument("--pages", type=int, default=1, help="키워드별 수집 페이지 수")
    parser.add_argument("--display", type=int, default=100, help="페이지당 공고 수")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    auth_key = get_work24_auth_key()
    if not auth_key:
        print("WORK24_AUTH_KEY 환경변수가 없습니다. .env.example을 참고해 인증키를 설정하세요.")
        raise SystemExit(1)

    keywords = args.keyword or DEFAULT_KEYWORDS
    saved = collect_work24_to_db(
        auth_key=auth_key,
        keywords=keywords,
        pages=args.pages,
        display=args.display,
    )

    print(f"검색 키워드: {', '.join(keywords)}")
    print(f"신규 저장: {saved}건")
    print(f"DB 경로: {get_db_path()}")


if __name__ == "__main__":
    main()
