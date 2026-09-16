"""Inspect derived evidence for a stored posting without fetching or modifying it."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jobskillradar.pipeline import load_posting_requirements


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect structured requirements from stored raw detail.")
    parser.add_argument("--source", default="work24", help="Posting source (default: work24).")
    parser.add_argument("--posting-id", required=True, help="Exact posting identity within the source.")
    parser.add_argument("--db-path", type=Path, help="Optional SQLite path; otherwise use the configured database.")
    args = parser.parse_args()
    result = load_posting_requirements(args.source, args.posting_id, db_path=args.db_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
