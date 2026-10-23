"""Portable source preparation and current-paper judge settings, without network/model calls."""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from secprbench.cli import _parser, _materialize
from secprbench.config import load_project, work_root
from secprbench.judge.runner import judge_task
from secprbench.judge.worker import complete
from secprbench.materialize.prepare import prepare_project
from secprbench.materialize.snapshot import history_blocked


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def test_project_paths_and_run_defaults_are_configurable(tmp_path, monkeypatch):
    monkeypatch.setenv("SECPRBENCH_REPOS_ROOT", str(tmp_path / "repos"))
    monkeypatch.setenv("SECPRBENCH_WORK_ROOT", str(tmp_path / "work"))
    monkeypatch.delenv("SECPRBENCH_CURL_REPO", raising=False)
    assert load_project("curl")["clone_dir"] == str(tmp_path / "repos/curl")
    monkeypatch.setenv("SECPRBENCH_CURL_REPO", str(tmp_path / "existing"))
    assert load_project("curl")["clone_dir"] == str(tmp_path / "existing")
    args = _parser().parse_args(["run", "--backend", "claude", "--output", "run"])
    assert args.roster == Path("data/roster.json")
    assert args.data_root == Path("data")
    assert args.work_root == work_root() == tmp_path / "work"


def test_prepare_and_materialize_local_source_without_history(tmp_path, monkeypatch):
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    git(upstream, "init", "-q")
    git(upstream, "config", "user.name", "Test")
    git(upstream, "config", "user.email", "test@example.invalid")
    (upstream / "a.c").write_text("int main(void) { return 0; }\n")
    git(upstream, "add", ".")
    git(upstream, "commit", "-qm", "Initial")
    commit = git(upstream, "rev-parse", "HEAD")
    initial_source = (upstream / "a.c").read_bytes()
    (upstream / "a.c").write_text("int main(void) { return 1; }\n")
    git(upstream, "commit", "-qam", "Companion revision")
    companion = git(upstream, "rev-parse", "HEAD")
    config_dir = tmp_path / "configs"
    (config_dir / "projects").mkdir(parents=True)
    (config_dir / "projects/curl.yaml").write_text(yaml.safe_dump({"name": "curl", "repo_url": str(upstream)}))
    monkeypatch.setenv("SECPRBENCH_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("SECPRBENCH_REPOS_ROOT", str(tmp_path / "repos"))
    monkeypatch.delenv("SECPRBENCH_CURL_REPO", raising=False)
    task = tmp_path / "task.json"
    task.write_text(json.dumps({"task_id": "test", "bug_id": "private-target", "task_type": "buggy",
                               "commit_sha": commit, "commit_message": "Initial", "pr_title": "Initial",
                               "files": [{"path": "a.c", "status": "added", "diff": "+int main(void);"}],
                               "ground_truth": {"root_cause": "private reference"}}))
    prepared = prepare_project("curl", task)
    assert prepared["cloned"] and prepared["commit"] == commit
    assert not prepare_project("curl", task)["cloned"]
    output = tmp_path / "materialized"
    _materialize(SimpleNamespace(task=task, project="curl", output=output))
    assert (output / "workspace/a.c").read_bytes() == initial_source
    assert history_blocked(output / "workspace")
    public = (output / "input/input.json").read_text()
    assert "private reference" not in public and "private-target" not in public
    benign = json.loads(task.read_text())
    benign.update(task_type="benign", commit_sha=companion)
    task.write_text(json.dumps(benign))
    assert prepare_project("curl", task)["commit"] == companion
    companion_output = tmp_path / "companion"
    _materialize(SimpleNamespace(task=task, project="curl", output=companion_output))
    assert (companion_output / "workspace/a.c").read_bytes() == (upstream / "a.c").read_bytes()
    assert history_blocked(companion_output / "workspace")
    assert "private reference" not in (companion_output / "input/input.json").read_text()
    assert git(upstream, "status", "--porcelain") == ""
    assert git(upstream, "rev-parse", "HEAD") == companion


def test_judge_enforces_cli_version_and_passes_effort(monkeypatch):
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        response = "2.1.283 (Claude Code)" if command[-1] == "--version" else '{"result":"verdict"}'
        return SimpleNamespace(returncode=0, stdout=response, stderr="")

    monkeypatch.setattr("secprbench.judge.worker.subprocess.run", run)
    request = {"model": "claude-opus-5-5", "prompt": "review", "paper_tools": False,
               "no_web": True, "reasoning_effort": "high", "claude_version": "2.1.283"}
    assert complete(request) == "verdict"
    assert commands[-1][commands[-1].index("--effort") + 1] == "high"
    request["claude_version"] = "2.1.258"
    with pytest.raises(ValueError, match="Expected Claude CLI 2.1.258"):
        complete(request)
    assert commands[-1][-1] == "--version"


def test_judge_effort_is_recorded_and_invalidates_resume(tmp_path):
    fixture = json.loads((Path(__file__).parent / "fixtures/judge_parity.json").read_text())
    calls = []

    def completion(prompt, **kwargs):
        calls.append(kwargs)
        return '{"detected": false}'

    args = (fixture["task"], fixture["task"]["ground_truth"], fixture["findings"], tmp_path)
    first = judge_task(*args, complete=completion)
    assert first["reasoning_effort"] == "high" and first["claude_version"] == "2.1.283"
    assert first["eval_model"] == "claude-opus-5-5"
    judge_task(*args, complete=completion)
    second = judge_task(*args, complete=completion, reasoning_effort="low")
    assert len(calls) == 2 and calls[-1]["reasoning_effort"] == "low"
    assert second["input_sha256"] != first["input_sha256"]
