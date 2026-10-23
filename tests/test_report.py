import copy
import json
import os
import tempfile
import unittest
from pathlib import Path

from secprbench.report.aggregate import aggregate, derive, derive_comparison
from secprbench.report.runs import cutoff_flag, season_for_date, summarize_runs, summarize_seasons
from secprbench.report.tables import write_paper_tables

BASE = Path(os.environ.get("SECPRBENCH_LEGACY_DATA_ROOT", str(Path(__file__).parent / "fixtures/unavailable-legacy"))) / "paper"
LEGACY = unittest.skipUnless((BASE / "baseline_results.json").is_file(),
                            "Set SECPRBENCH_LEGACY_DATA_ROOT for historical paper statistics")


class ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if (BASE / "baseline_results.json").is_file():
            cls.snapshot = json.loads((BASE / "baseline_results.json").read_text())

    @LEGACY
    def test_exact_frozen_paper_statistics_and_comparison(self):
        actual = derive(self.snapshot)
        self.assertEqual(actual, json.loads((BASE / "baseline_derived.json").read_text()))
        self.assertEqual(
            derive_comparison(self.snapshot, actual),
            json.loads((BASE / "comparison_analysis.json").read_text()),
        )
        self.assertEqual(
            [actual["models"][m]["buggy"]["detected"] for m in actual["models"]], [129, 121, 96, 51, 114]
        )
        self.assertEqual(actual["models"]["gpt"]["benign"]["unscanned"], 120)

    @LEGACY
    def test_tables_and_incomplete_benign_exclusion(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            write_paper_tables(self.snapshot, out)
            self.assertEqual(len(list(out.glob("*.tex"))), 10)
            self.assertIn("Claude Opus 5 & 129 & 80.6", (out / "baseline_main_rows.tex").read_text())
            self.assertNotIn("GPT-5.6", (out / "baseline_fixed_rows.tex").read_text())

    @LEGACY
    def test_duplicate_or_missing_assignments_fail(self):
        snapshot = copy.deepcopy(self.snapshot)
        snapshot["results"].pop()
        with self.assertRaises(ValueError):
            derive(snapshot)
        snapshot = copy.deepcopy(self.snapshot)
        snapshot["cases"].append(snapshot["cases"][0])
        with self.assertRaises(ValueError):
            derive(snapshot)

    @LEGACY
    def test_output_token_rule_and_denominator(self):
        rows = [copy.deepcopy(self.snapshot["results"][0]) for _ in range(2)]
        rows[0].update(
            scanned=False,
            judged=False,
            detected=False,
            status="no_output_recorded",
            usage={"output_tokens": 0},
        )
        rows[1].update(
            scanned=True,
            judged=True,
            detected=True,
            status="positive_verdict",
            reports=1,
            usage={"output_tokens": 20},
        )
        result = aggregate(rows)
        self.assertEqual((result["assigned"], result["scanned"], result["detected"]), (2, 1, 1))
        self.assertEqual(result["usage"]["output_tokens"], 20)
        self.assertIsNone(result["median_minutes"])

    @LEGACY
    def test_season_boundaries_and_cutoff_flags(self):
        self.assertEqual(
            [season_for_date(x) for x in ("2025-06-30", "2025-07-01", None)], ["2025H1", "2025H2", "unknown"]
        )
        self.assertEqual(cutoff_flag("2025H1", "2025-06-30"), "pre_cutoff")
        self.assertEqual(cutoff_flag("2025H2", "2025-06-30"), "post_cutoff")
        self.assertEqual(cutoff_flag("2025H1", "2025-03-01"), "straddles_cutoff")
        seasons = {f"{c['project']}/{c['bug_id']}": "2025H2" for c in self.snapshot["cases"]}
        result = summarize_seasons(self.snapshot, case_seasons=seasons, model_cutoffs={"opus": "2025-06-30"})
        self.assertEqual(len(result), 10)
        opus = next(r for r in result if r["model"] == "opus" and r["task_type"] == "buggy")
        self.assertEqual(opus["cutoff_flag"], "post_cutoff")
        self.assertEqual(opus["recall"], 129 / 160)

    def test_pending_assignments_stay_in_denominator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assignments = [
                {
                    "project": "curl",
                    "task_id": str(i),
                    "bug_id": str(i),
                    "task_type": "buggy",
                    "fix_date": "2025-07-01",
                }
                for i in range(3)
            ]
            (root / "manifest.json").write_text(
                json.dumps({"backend": "opus", "harness": "direct", "tasks": [], "assignments": assignments})
            )
            group = summarize_runs([root])["groups"][0]
            self.assertEqual(
                (group["assigned"], group["scanned"], group["pending"], group["failed"]), (3, 0, 3, 0)
            )
            self.assertEqual(group["recall"], 0)

    def test_malformed_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for manifest in (
                {"tasks": {}},
                {"tasks": [{"task_id": "x"}]},
                {"tasks": [], "assignments": [{"task_id": "x"}]},
                {"tasks": [{"project": "curl", "task_id": "x", "output_dir": "out"}], "assignments": []},
            ):
                (root / "manifest.json").write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):
                    summarize_runs([root])

    def test_native_run_retains_failure_and_rejects_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records = []
            for num, status in enumerate(("succeeded", "failed")):
                out = root / str(num) / "out"
                out.mkdir(parents=True)
                task = root / f"task{num}.json"
                task.write_text(json.dumps({"fix_date": "2025-07-01"}))
                record = {
                    "task_id": str(num),
                    "task_path": str(task),
                    "output_dir": str(out),
                    "status": status,
                    "project": "curl",
                    "bug_id": str(num),
                    "task_type": "buggy",
                    "usage": {"output_tokens": 100 if num == 0 else 0},
                }
                records.append(record)
                if num == 0:
                    (out / "findings.json").write_text(
                        json.dumps({"predictions": [{"title": "finding", "file": "a.c"}]})
                    )
                    (out / "verdict.json").write_text(
                        json.dumps({"detected": True, "completed": True, "error": False, "num_findings": 1})
                    )
            (root / "manifest.json").write_text(
                json.dumps({"backend": "opus", "harness": "direct", "tasks": records})
            )
            # A reviewer-owned verdict file cannot manufacture a benchmark hit.
            unjudged = summarize_runs([root], model_cutoffs={"opus": "2025-06-30"})
            self.assertEqual(unjudged["groups"][0]["detected"], 0)
            (root / "judge_summary.json").write_text(
                json.dumps(
                    {"evals": {"0": {"detected": True, "completed": True, "error": False, "num_findings": 1}}}
                )
            )
            summary = summarize_runs([root], model_cutoffs={"opus": "2025-06-30"})
            group = summary["groups"][0]
            self.assertEqual(
                (group["assigned"], group["scanned"], group["failed"], group["recall"]), (2, 1, 1, 0.5)
            )
            self.assertEqual(group["cutoff_flag"], "post_cutoff")
            with self.assertRaises(ValueError):
                summarize_runs([root, root])


if __name__ == "__main__":
    unittest.main()
