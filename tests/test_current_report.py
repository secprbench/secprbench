"""The published frozen evidence must reproduce its membership-filtered counts."""

import json
from pathlib import Path

import pytest

from secprbench.cli import main
from secprbench.report.aggregate import derive
from secprbench.report.snapshot import normalize_snapshot

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "artifacts/results/results_265_opus55_high.json"


def test_current_report_cli_matches_every_published_arm(tmp_path):
    assert main(["report", "--snapshot", str(SNAPSHOT), "--out", str(tmp_path)]) == 0
    derived = json.loads((tmp_path / "baseline_derived.json").read_text())
    published = json.loads((ROOT / "artifacts/results/summary_265.json").read_text())
    assert derived["buggy"] == derived["benign"] == published["case_count"] == 265
    assert derived["instances"] == 530
    for arm in published["by_model_and_task_type"]:
        actual = derived["models"][arm["model"]][arm["task_type"]]
        assert {key: actual[key] for key in ("assigned", "scanned", "judged")} == {
            key: arm[key] for key in ("assigned", "scanned", "judged")}
        assert actual["detected"] == arm["target_hits"]
    assert "not calibrated false-positive rates" in derived["interpretation"]
    assert "Claude Opus 5.5 (high)" in (tmp_path / "recall.md").read_text()


@pytest.mark.parametrize("duplicate", [False, True])
def test_current_report_rejects_missing_and_duplicate_assignments(duplicate):
    snapshot = json.loads(SNAPSHOT.read_text())
    if duplicate:
        snapshot["records"][-1] = snapshot["records"][0]
    else:
        snapshot["records"].pop()
    with pytest.raises(ValueError, match="Results do not match roster"):
        derive(normalize_snapshot(snapshot))


def test_current_report_preserves_judge_and_scoring_evidence():
    snapshot = json.loads(SNAPSHOT.read_text())
    normalized = normalize_snapshot(snapshot)
    for original, row in zip(snapshot["records"], normalized["results"]):
        assert row["detected"] is original["detected"]
        assert row["matched"] is original["matched"]
        assert row["judge"] == (original.get("judge") or {})
    assert "cases" not in snapshot and "results" not in snapshot
