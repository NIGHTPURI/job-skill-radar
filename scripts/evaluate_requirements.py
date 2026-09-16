"""Evaluate committed manual labels without network, keys, or SQLite."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from jobskillradar.requirement_evaluation import evaluate_requirements


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path,
                        default=ROOT / "tests/fixtures/requirements/evaluation.json")
    parser.add_argument("--json", action="store_true", help="Print the full deterministic report as JSON.")
    args = parser.parse_args()
    raw = args.fixtures.read_bytes()
    report = evaluate_requirements(json.loads(raw))
    report["corpus_sha256"] = hashlib.sha256(raw).hexdigest()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("Fixture evaluation only; NOT real-world or production accuracy.")
        print(f"Exact cases: {report['exact_cases']}/{report['cases']}; "
              f"exact skill classifications: {report['exact_matches']}/{report['expected_results']}; "
              f"classification mismatches: {report['classification_mismatches']}")
        for kind, values in report["per_class"].items():
            ratios = " ".join(f"fixture_{name}={values['fixture_' + name]:.3f}"
                              if values['fixture_' + name] is not None else f"fixture_{name}=N/A"
                              for name in ("precision", "recall", "f1"))
            print(f"{kind}: {ratios} FP={values['false_positives']} FN={values['false_negatives']}")
        print(f"Required false positives: {report['required_false_positives']}; "
              f"preferred false positives: {report['preferred_false_positives']}")
        print(f"Groups: {json.dumps(report['groups'], sort_keys=True)}")
        for mismatch in report["mismatches"]:
            print("MISMATCH " + json.dumps(mismatch, ensure_ascii=False, sort_keys=True))
        print("Gate: " + ("PASS" if report["passed"] else "FAIL") + " (all reviewed labels must match)")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
