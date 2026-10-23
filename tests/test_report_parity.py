"""Precise prompt exceptions and complete assignment accounting for comparisons."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from secprbench.harnesses.direct_review.prompts import build_user_prompt
from secprbench.io import sha256_file
from secprbench.materialize.review_input import public_review_metadata
from secprbench.report.parity import _prompt_comparison, compare_run


def task(kind="buggy", prefix=""):
    return {
        "task_id": "task" + ("_benign" if kind == "benign" else ""),
        "task_type": kind,
        "commit_message": prefix + "Original change",
        "intro_commit_message": "Original change",
        "pr_title": prefix + "Original change",
        "files": [{"path": "a.c", "status": "modified", "diff": "@@ -1 +1 @@\n-old\n+new\n"}],
    }


def write_prompts(root: Path, source: dict, actual: str | None = None):
    archive, out = root / "archive", root / "out"
    (archive / "logs").mkdir(parents=True)
    out.mkdir()
    trajectory = archive / "logs/scan.traj.json"
    trajectory.write_text(
        json.dumps(
            {
                "system_prompt": "Review source in /original/workspace.",
                "metadata": {"project_directory": "/original/workspace"},
                "turns": [{"input": build_user_prompt(source)}],
            }
        )
    )
    (out / "system_prompt.md").write_text("Review source in /workspace.")
    (out / "user_prompt.md").write_text(actual if actual is not None else build_user_prompt(source))
    return archive, out, trajectory


def test_raw_exact_equality_remains_distinct_from_exceptions(tmp_path):
    source = task()
    archive, out, _ = write_prompts(tmp_path, source)
    result = _prompt_comparison(out, archive, archived_task=source)
    assert result["system_equal"]
    assert result["first_user_equal"]
    assert result["first_user_compatible"]
    assert result["first_user_classification"] == "exact"
    assert result["intentional_metadata_scrub"] is False


@pytest.mark.parametrize("prefix", ["[Merged] ", "Merged: ", "[Benign] "])
def test_only_production_metadata_scrub_is_allowed(tmp_path, prefix):
    source = task("benign", prefix)
    sanitized = {**source, **public_review_metadata(source)}
    archive, out, _ = write_prompts(tmp_path, source, build_user_prompt(sanitized))
    original = copy.deepcopy(source)
    result = _prompt_comparison(out, archive, archived_task=source)
    assert result["first_user_equal"] is False
    assert result["first_user_compatible"]
    assert result["first_user_classification"] == "intentional_metadata_scrub"
    assert result["intentional_metadata_scrub"]
    assert result["scrub_check"] == "archived_input_reproduced"
    assert "commit_message" in result["scrubbed_metadata_fields"]
    assert source == original


@pytest.mark.parametrize(
    "mutation", [lambda text: text + "\n", lambda text: text.replace("+new", "+different")]
)
def test_wrapper_removal_does_not_hide_unexpected_prompt_changes(tmp_path, mutation):
    source = task("benign", "[Merged] ")
    sanitized = {**source, **public_review_metadata(source)}
    archive, out, _ = write_prompts(tmp_path, source, mutation(build_user_prompt(sanitized)))
    result = _prompt_comparison(out, archive, archived_task=source)
    assert result["first_user_classification"] == "unexpected_mismatch"
    assert result["first_user_compatible"] is False
    assert result["intentional_metadata_scrub"] is False


def test_genuine_upstream_prefix_is_not_an_intentional_scrub(tmp_path):
    source = task("benign", "[Merged] ")
    source["intro_commit_message"] = source["commit_message"]
    changed = {**source, "commit_message": "Original change"}
    archive, out, _ = write_prompts(tmp_path, source, build_user_prompt(changed))
    result = _prompt_comparison(out, archive, archived_task=source)
    assert result["first_user_classification"] == "unexpected_mismatch"
    assert result["intentional_metadata_scrub"] is False


def test_scrub_requires_reconstructable_archived_input(tmp_path):
    source = task("benign", "[Merged] ")
    sanitized = {**source, **public_review_metadata(source)}
    archive, out, _ = write_prompts(tmp_path, source, build_user_prompt(sanitized))
    wrong_source = {**source, "commit_message": "[Merged] A different original"}
    result = _prompt_comparison(out, archive, archived_task=wrong_source)
    assert result["scrub_check"] == "archived_input_not_reproduced"
    assert result["first_user_compatible"] is False


def test_missing_prompt_artifacts_are_unavailable(tmp_path):
    result = _prompt_comparison(tmp_path / "absent-output", tmp_path / "absent-archive")
    assert result["available"] is False
    assert "first_user_equal" not in result


def comparison_fixture(root: Path, *, benign=False, pending=False):
    source = task("benign", "[Merged] ") if benign else task()
    sanitized = {**source, **public_review_metadata(source)}
    archive, out, trajectory = write_prompts(root, source, build_user_prompt(sanitized))
    task_file = root / "original-task.json"
    task_file.write_text(json.dumps(source))
    identity = {
        "project": "curl",
        "bug_id": "case",
        "task_id": source["task_id"],
        "task_type": source["task_type"],
    }
    record = {**identity, "status": "succeeded", "output_dir": "out", "finding_count": 0}
    assignments = [identity]
    if pending:
        assignments.append({**identity, "bug_id": "pending-case", "task_id": "pending-task"})
    (root / "manifest.json").write_text(
        json.dumps(
            {"backend": "opus", "harness": "direct_review", "tasks": [record], "assignments": assignments}
        )
    )
    snapshot = {
        "cases": [
            {
                "project": "curl",
                "bug_id": "case",
                source["task_type"]: {"source": task_file.name, "sha256": sha256_file(task_file)},
            }
        ],
        "results": [
            {
                "model": "opus",
                "project": "curl",
                "bug_id": "case",
                "task_type": source["task_type"],
                "source": archive.name,
                "reports": 0,
                "detected": False,
                "usage": {},
            }
        ],
        "source_files": {str(trajectory.relative_to(root)): sha256_file(trajectory)},
    }
    snapshot_path = root / "frozen.json"
    snapshot_path.write_text(json.dumps(snapshot))
    return snapshot_path, trajectory, task_file


def test_pending_assignments_prevent_partial_prompt_gate_from_passing(tmp_path):
    snapshot, _, _ = comparison_fixture(tmp_path, pending=True)
    result = compare_run(tmp_path, snapshot, tmp_path)
    assert result["assigned"] == len(result["rows"]) == 2
    assert result["completed_records"] == 1
    assert result["pending"] == result["unavailable_prompt_pairs"] == 1
    assert result["compared_prompt_pairs"] == 1
    assert result["prompts_equal"] is True  # Raw metric explicitly covers available comparisons.
    assert result["prompt_coverage_complete"] is False
    assert result["prompt_contract_satisfied"] is False
    assert result["rows"][0]["archived"]["wall_seconds"] is None


def test_frozen_task_provenance_and_raw_vs_intentional_gate(tmp_path):
    snapshot, _, task_file = comparison_fixture(tmp_path, benign=True)
    result = compare_run(tmp_path, snapshot, tmp_path)
    assert result["prompts_equal"] is False
    assert result["intentional_metadata_scrubs"] == 1
    assert result["unexpected_prompt_mismatches"] == 0
    assert result["prompt_contract_satisfied"] is True
    task_file.write_text(task_file.read_text() + "\n")
    changed = compare_run(tmp_path, snapshot, tmp_path)
    assert changed["prompt_contract_satisfied"] is False
    assert changed["intentional_metadata_scrubs"] == 0
    assert changed["rows"][0]["prompt_parity"]["scrub_check"] == "archived_task_unavailable"


def test_mutated_archived_trajectory_is_not_frozen_prompt_evidence(tmp_path):
    snapshot, trajectory, _ = comparison_fixture(tmp_path)
    trajectory.write_text(trajectory.read_text() + "\n")
    result = compare_run(tmp_path, snapshot, tmp_path)
    assert result["compared_prompt_pairs"] == 0
    assert result["prompts_equal"] is None
    assert result["prompt_contract_satisfied"] is False
    assert result["rows"][0]["prompt_parity"]["reason"] == "archived trajectory changed since frozen capture"


def test_empty_run_has_no_vacuous_parity_success(tmp_path):
    (tmp_path / "manifest.json").write_text(
        json.dumps({"backend": "opus", "harness": "direct_review", "tasks": [], "assignments": []})
    )
    (tmp_path / "snapshot.json").write_text('{"results": []}')
    result = compare_run(tmp_path, tmp_path / "snapshot.json")
    assert result["assigned"] == 0
    assert result["prompts_equal"] is None
    assert result["prompt_contract_satisfied"] is None
