import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from jobskillradar.requirement_evaluation import evaluate_requirements

CORPUS = ROOT / "tests/fixtures/requirements/evaluation.json"


def case(expected=None, **overrides):
    return {"id": "manual", "review_note": "Explicit synthetic labels.", "detail": {},
            "expected": expected or {}, "quality": "requirements_extracted", **overrides}


def result(skills=None, groups=None, quality="requirements_extracted"):
    return {"extractor_version": 2, "skills": [
        {"skill": skill, "requirement_type": kind} for skill, kind in (skills or [])],
        "groups": groups or [], "quality_status": quality}


class RequirementEvaluationTest(unittest.TestCase):
    def test_fractional_metrics_count_wrong_classes_as_fp_and_fn(self):
        labels = [case({"Java": "required", "SQL": "required", "Docker": "preferred"})]
        actual = result([("Java", "required"), ("Python", "required"), ("Docker", "unspecified")])
        report = evaluate_requirements(labels, extractor=lambda _: actual)
        self.assertEqual((report["expected_results"], report["actual_results"], report["exact_matches"]), (3, 3, 1))
        self.assertEqual(report["per_class"]["required"], {
            "true_positives": 1, "false_positives": 1, "false_negatives": 1,
            "fixture_precision": .5, "fixture_recall": .5, "fixture_f1": .5})
        self.assertEqual(report["preferred_false_positives"], 0)
        self.assertEqual(report["per_class"]["preferred"]["false_negatives"], 1)
        self.assertEqual(report["per_class"]["unspecified"]["false_positives"], 1)
        self.assertEqual(report["classification_mismatches"], 1)
        self.assertEqual(report["mismatches"][0]["classification_mismatches"],
                         [{"skill": "Docker", "expected": "preferred", "actual": "unspecified"}])
        self.assertFalse(report["passed"])

    def test_required_and_preferred_false_positives_are_explicit(self):
        report = evaluate_requirements([case({"Java": "unspecified", "Docker": "unspecified"})],
                                       extractor=lambda _: result([("Java", "required"), ("Docker", "preferred")]))
        self.assertEqual(report["required_false_positives"], 1)
        self.assertEqual(report["preferred_false_positives"], 1)
        self.assertEqual(report["per_class"]["unspecified"]["false_negatives"], 2)

    def test_no_positive_predictions_does_not_pass_by_hiding_false_negatives(self):
        report = evaluate_requirements([case({"Java": "required"})], extractor=lambda _: result())
        metrics = report["per_class"]["required"]
        self.assertIsNone(metrics["fixture_precision"])
        self.assertEqual((metrics["fixture_recall"], metrics["fixture_f1"]), (0, 0))
        self.assertEqual(report["required_false_positives"], 0)
        self.assertFalse(report["passed"])

    def test_absent_classes_report_undefined_ratios_not_perfect_accuracy(self):
        report = evaluate_requirements([case({"Java": "required"})],
                                       extractor=lambda _: result([("Java", "required")]))
        self.assertTrue(report["passed"])
        for metric in ("fixture_precision", "fixture_recall", "fixture_f1"):
            self.assertIsNone(report["per_class"]["preferred"][metric])

    def test_duplicate_predictions_are_false_positives(self):
        report = evaluate_requirements([case({"Java": "required"})],
                                       extractor=lambda _: result([("Java", "required")] * 2))
        self.assertEqual(report["required_false_positives"], 1)
        self.assertEqual(report["exact_matches"], 1)
        self.assertFalse(report["passed"])

    def test_wrong_group_relation_is_visible_even_when_skill_classes_match(self):
        skills = {"Java": "unspecified", "Kotlin": "unspecified"}
        expected = {"relation": "any_of", "requirement_type": "required", "skills": list(skills)}
        actual = {**expected, "relation": "all_of"}
        report = evaluate_requirements([case(skills, expected_groups=[expected])],
                                       extractor=lambda _: result(list(skills.items()), [actual]))
        self.assertEqual(report["exact_matches"], 2)
        self.assertEqual(report["groups"]["false_positives"], 1)
        self.assertEqual(report["groups"]["false_negatives"], 1)
        self.assertEqual(report["required_false_positives"], 1)
        self.assertEqual(report["group_per_class"]["required"]["false_positives"], 1)
        self.assertFalse(report["passed"])

    def test_groups_compare_members_class_and_multiplicity_but_not_member_order(self):
        skills = {"Java": "unspecified", "Kotlin": "unspecified"}
        group = {"relation": "any_of", "requirement_type": "preferred", "skills": list(skills)}
        labels = [case(skills, expected_groups=[group])]
        reversed_group = {**group, "skills": list(reversed(group["skills"]))}
        report = evaluate_requirements(labels, extractor=lambda _: result(list(skills.items()), [reversed_group]))
        self.assertTrue(report["passed"])
        for groups in ([], [group, group], [{**group, "requirement_type": "required"}],
                       [{**group, "skills": ["Java", "SQL"]}]):
            with self.subTest(groups=groups):
                report = evaluate_requirements(labels, extractor=lambda _: result(list(skills.items()), groups))
                self.assertFalse(report["passed"])
        self.assertEqual(report["preferred_false_positives"], 1)

    def test_quality_mismatch_fails_even_with_no_skill_errors(self):
        report = evaluate_requirements([case({}, quality="detail_not_fetched", detail=None)],
                                       extractor=lambda _: result(quality="detail_fetched_but_no_requirement_evidence"))
        self.assertEqual(report["exact_matches"], 0)
        self.assertEqual(report["classification_mismatches"], 0)
        self.assertEqual(len(report["mismatches"]), 1)
        self.assertFalse(report["passed"])

    def test_invalid_labels_are_rejected_instead_of_silently_skipped(self):
        for labels in ([], [case(), case()], [case({"Elixir": "required"})],
                       [case({"Java": "maybe"})], [case(review_note=" ")],
                       [case(quality="complete")],
                       [case({"Java": "required"}, expected_groups=[
                           {"relation": "any_of", "skills": ["Java"], "requirement_type": "required"}])]):
            with self.subTest(labels=labels), self.assertRaises(ValueError):
                evaluate_requirements(labels)

    def test_committed_corpus_gate_is_deterministic_without_io_or_input_mutation(self):
        labels = json.loads(CORPUS.read_text(encoding="utf-8"))
        original = copy.deepcopy(labels)
        with patch("urllib.request.urlopen", side_effect=AssertionError("Unexpected HTTP")), \
                patch("sqlite3.connect", side_effect=AssertionError("Unexpected SQLite")):
            report = evaluate_requirements(labels)
            self.assertEqual(report, evaluate_requirements(labels))
        self.assertEqual(labels, original)
        self.assertEqual((report["cases"], report["exact_cases"]), (60, 60))
        self.assertEqual((report["expected_results"], report["exact_matches"]), (144, 144))
        self.assertEqual(report["groups"]["true_positives"], 13)
        self.assertEqual((report["required_false_positives"], report["preferred_false_positives"]), (0, 0))
        self.assertEqual(report["extractor_versions"], [2])
        self.assertTrue(report["passed"])

    def test_extraction_errors_propagate_instead_of_counting_empty_success(self):
        def fail(_):
            raise RuntimeError("injected extraction failure")
        with self.assertRaisesRegex(RuntimeError, "injected"):
            evaluate_requirements([case()], extractor=fail)

    def test_cli_reports_metrics_mismatches_and_exit_codes(self):
        cli = [sys.executable, "-B", str(ROOT / "scripts/evaluate_requirements.py")]
        completed = subprocess.run(cli, capture_output=True, text=True, cwd=ROOT, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Fixture evaluation only", completed.stdout)
        self.assertIn("Required false positives: 0", completed.stdout)
        self.assertIn("Gate: PASS", completed.stdout)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "labels.json"
            path.write_text(json.dumps([case({"Java": "unspecified"}, detail={"job_content": "Java required"})]), encoding="utf-8")
            failed = subprocess.run([*cli, "--fixtures", str(path)], capture_output=True, text=True, cwd=ROOT, check=False)
            self.assertEqual(failed.returncode, 1, failed.stderr)
            self.assertIn("Required false positives: 1", failed.stdout)
            self.assertIn("MISMATCH", failed.stdout)
            structured = subprocess.run([*cli, "--fixtures", str(path), "--json"], capture_output=True, text=True, cwd=ROOT, check=False)
            self.assertEqual(structured.returncode, 1)
            report = json.loads(structured.stdout)
            self.assertFalse(report["passed"])
            self.assertEqual(len(report["corpus_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
