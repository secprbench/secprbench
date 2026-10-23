"""Exercise complete host state transitions without spending inference budget."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from secprbench.config import BackendSpec
from secprbench.harnesses.contract import HarnessSpec
from secprbench.ids import opaque_id
from secprbench.io import write_json, sha256_file
from secprbench.sandbox import runner


def task_file(root):
    path = root / "task.json"
    write_json(
        path,
        {
            "task_id": "pr_review_private",
            "bug_id": "private",
            "commit_sha": "a" * 40,
            "task_type": "buggy",
            "files": [{"path": "x.c", "status": "modified"}],
            "full_diff": "diff",
        },
    )
    return path


@pytest.mark.parametrize(
    "outcome,status",
    [
        ("valid", "succeeded"),
        ("zero", "failed"),
        ("malformed", "failed"),
        ("symlink", "failed"),
        ("timeout", "failed"),
    ],
)
def test_run_task_validation_cleanup_and_private_mapping(tmp_path, monkeypatch, outcome, status):
    task = task_file(tmp_path)
    monkeypatch.setattr(runner, "materialize_snapshot", lambda repo, sha, path: path.mkdir())
    monkeypatch.setattr(runner, "_credential_file", lambda *args: None)
    monkeypatch.setattr(runner, "docker_command", lambda *args, **kw: ([], {}))
    run_id = opaque_id(b"a" * 32, "curl/pr_review_private")

    def execute(command, env, out, timeout, **kwargs):
        if outcome == "symlink":
            (out / "findings.json").symlink_to(tmp_path / "secret")
        else:
            result = {"instance_id": run_id, "model": "test", "predictions": [], "tokens_out": 3}
            if outcome == "zero":
                result["tokens_out"] = 0
            if outcome == "malformed":
                result["predictions"] = "invalid"
            write_json(out / "findings.json", result)
        return {
            "exit_code": 124 if outcome == "timeout" else 0,
            "timed_out": outcome == "timeout",
            "oom_killed": False,
            "client_ip": None,
            "started_at": 1,
            "finished_at": 2,
            "wall_seconds": 1,
        }

    monkeypatch.setattr(runner, "execute_container", execute)
    # FIFO would block if followed. The audit must fail before opening this link.
    import os

    os.mkfifo(tmp_path / "secret")
    record = runner.run_task(
        task_path=task,
        project="curl",
        run_dir=tmp_path / "run",
        secret=b"a" * 32,
        backend=BackendSpec(name="test", model="test", egress_hosts=["api.example.com"]),
        harness=HarnessSpec(name="direct_review", image="test", command=["true"]),
        network="internal",
        proxy_ip="172.20.0.2",
        proxy_log=tmp_path / "proxy.log",
    )
    assert record["status"] == status
    assert not (tmp_path / "run" / run_id / "workspace").exists()
    assert (tmp_path / "run" / run_id / "record.json").is_file()
    if outcome == "symlink":
        assert record["audit_events"][0]["event"] == "output_symlink"


def test_resume_binds_task_output_and_image_hashes(tmp_path, monkeypatch):
    task = task_file(tmp_path)
    roster = tmp_path / "roster.json"
    write_json(
        roster,
        {
            "entries": [
                {
                    "project": "curl",
                    "bug_id": "private",
                    "source": "verified",
                    "buggy": {"path": str(task), "sha256": sha256_file(task)},
                    "benign": {"path": str(task), "sha256": sha256_file(task)},
                }
            ]
        },
    )
    monkeypatch.setattr(runner, "start_proxy", lambda *args: ("internal", "172.20.0.2"))
    monkeypatch.setattr(runner.subprocess, "run", lambda *args, **kw: SimpleNamespace(stdout="sha256:image"))
    calls = []

    def run_task(**kw):
        calls.append(1)
        out = kw["run_dir"] / opaque_id(kw["secret"], "curl/pr_review_private") / "out"
        write_json(out / "findings.json", {"instance_id": "123456abcdef", "model": "test", "predictions": []})
        return {
            "task_id": "pr_review_private",
            "bug_id": "private",
            "project": "curl",
            "task_type": "buggy",
            "task_sha256": sha256_file(task),
            "output_dir": str(out),
            "status": "succeeded",
            "findings_sha256": sha256_file(out / "findings.json"),
        }

    monkeypatch.setattr(runner, "run_task", run_task)
    options = dict(
        roster=roster,
        data_root=tmp_path,
        backend_name="opus",
        harness_name="direct_review",
        run_dir=tmp_path / "run",
        work_root=tmp_path / "work",
        limit=1,
        concurrency=1,
    )
    first = runner.run_roster(**options)
    assert len(first["assignments"]) == 1 and "opaque_id" not in first["assignments"][0]
    runner.run_roster(**options)
    assert len(calls) == 1
    write_json(Path(first["tasks"][0]["output_dir"]) / "findings.json", {"tampered": True})
    runner.run_roster(**options)
    assert len(calls) == 2 and list((tmp_path / "run/attempts").iterdir())
    monkeypatch.setattr(
        runner.subprocess, "run", lambda *args, **kw: SimpleNamespace(stdout="sha256:rebuilt")
    )
    with pytest.raises(ValueError, match="configuration changed"):
        runner.run_roster(**options)
