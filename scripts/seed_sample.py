from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jobskillradar.config import get_db_path
from jobskillradar.pipeline import seed_sample_db


def main() -> None:
    saved = seed_sample_db()
    print(f"샘플 데이터 저장 완료: 신규 {saved}건")
    print(f"DB 경로: {get_db_path()}")


if __name__ == "__main__":
    main()
