"""Byte-level parity against the actual archived paper runs."""

import json
import os
from pathlib import Path

import pytest

from secprbench.harnesses.direct_review import build_system_prompt, build_user_prompt
from secprbench.materialize.review_input import build_review_input

PROJECTS = ("curl", "openssl", "freetype", "v8", "firefox", "ffmpeg", "redis", "sqlite", "wasmtime")
ARCHIVE = Path(os.environ.get("SECPRBENCH_ARCHIVE_ROOT", Path(__file__).parent / "fixtures/unavailable-archive"))


@pytest.mark.integration
@pytest.mark.parametrize("project", PROJECTS)
def test_all_archived_direct_review_prompts(project):
    logs = sorted(
        (ARCHIVE / "bench" / f"pr_bench_{project}" / "bench_base_recall_opus").glob(
            "bug_*/logs/pr_review_*.traj.json"
        )
    )
    if not logs:
        pytest.skip("local archived trajectories are unavailable")
    for log in logs:
        archived = json.loads(log.read_text())
        task_path = (
            ARCHIVE / "cgsa_datasets" / project / "pr_tasks" / (archived["metadata"]["task_id"] + ".json")
        )
        task = json.loads(task_path.read_text())
        original_path = archived["metadata"]["project_directory"]
        assert build_system_prompt() == archived["system_prompt"].replace(original_path, "/workspace"), str(
            log
        )
        assert build_user_prompt(build_review_input(task)) == archived["turns"][0]["input"], str(log)


def test_untracked_prompt_has_no_progress_requirement():
    text = build_system_prompt(coverage_tracking=False)
    assert "## Coverage Tracking" not in text
    assert "Track your own progress" in text


def test_user_prompt_receives_scrubbed_metadata():
    task = {"task_type": "benign", "commit_message": "[Merged] Original change", "files": []}
    assert "[Merged]" not in build_user_prompt(build_review_input(task))
    assert "Original change" in build_user_prompt(build_review_input(task))


def test_explicit_context_preserves_surrounding_template():
    text = build_system_prompt(project_context="## Project\nContext")
    assert "\n\n## Project\nContext\n\n\n## Project Environment" in text
    assert "__SECPRBENCH_" not in text


def test_portable_archived_prompt_fixture():
    fixture = json.loads((Path(__file__).parent / "fixtures/harness/paper_direct_review.json").read_text())
    assert build_system_prompt() == fixture["system_prompt"]
    assert build_user_prompt(fixture["review_input"]) == fixture["user_prompt"]
