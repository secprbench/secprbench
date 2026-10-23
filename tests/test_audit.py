"""Completed reviews can be rechecked without relaxing execution requirements."""

import fcntl
import subprocess

import pytest

from secprbench.io import read_json, sha256_file, write_json
from secprbench.ids import scan_outputs
from secprbench.sandbox.audit import recheck_run


def failed_run(tmp_path):
    task = tmp_path / "task.json"
    write_json(
        task,
        {
            "task_id": "pr_review_secret",
            "bug_id": "secret",
            "task_type": "buggy",
            "files": [{"path": "x.c", "status": "modified"}],
            "full_diff": "diff",
        },
    )
    root = tmp_path / "run"
    out = root / "012345abcdef/out"
    write_json(
        out / "findings.json",
        {"instance_id": "012345abcdef", "model": "test", "predictions": [], "tokens_out": 10},
    )
    (out / "trajectory.json").write_text('{"task_type":"local_agent"}')
    record = {
        "task_id": "pr_review_secret",
        "opaque_id": "012345abcdef",
        "status": "failed",
        "exit_code": 0,
        "task_path": str(task),
        "task_sha256": sha256_file(task),
        "output_dir": str(out),
        "error": "old audit false positive",
        "audit_events": [{"event": "construction_marker", "path": "trajectory.json"}],
    }
    write_json(root / "manifest.json", {"harness": "defending", "tasks": [record]})
    return root, out, task


def test_recheck_preserves_failure_provenance_and_updates_record(tmp_path):
    root, out, _ = failed_run(tmp_path)
    assert recheck_run(root)["revalidated"] == ["pr_review_secret"]
    record = read_json(root / "manifest.json")["tasks"][0]
    assert record == read_json(out.parent / "record.json")
    assert record["status"] == "succeeded"
    assert record["findings_sha256"] == sha256_file(out / "findings.json")
    assert record["revalidation"]["previous_error"] == "old audit false positive"
    assert record["revalidation"]["previous_audit_events"][0]["event"] == "construction_marker"
    assert recheck_run(root)["revalidated"] == []


@pytest.mark.parametrize(
    "failure",
    [
        "timeout",
        "oom",
        "exit",
        "denied",
        "leak",
        "hash",
        "missing",
        "schema",
        "object",
        "prediction",
        "location",
        "zero",
        "symlink",
    ],
)
def test_recheck_cannot_erase_real_failures(tmp_path, failure):
    root, out, task = failed_run(tmp_path)
    manifest = read_json(root / "manifest.json")
    record = manifest["tasks"][0]
    if failure in {"timeout", "oom", "exit", "denied"}:
        field, value = {
            "timeout": ("timed_out", True),
            "oom": ("oom_killed", True),
            "exit": ("exit_code", 1),
            "denied": ("audit_events", [{"event": "denied_egress"}]),
        }[failure]
        record[field] = value
        write_json(root / "manifest.json", manifest)
    elif failure == "leak":
        (out / "trajectory.json").write_text('{"task_type":"buggy"}')
    elif failure == "hash":
        task.write_text("changed")
    elif failure == "missing":
        task.unlink()
    elif failure == "symlink":
        (out / "findings.json").unlink()
        (out / "findings.json").symlink_to(task)
    else:
        findings = read_json(out / "findings.json")
        if failure == "object":
            findings = ["invalid"]
        elif failure == "schema":
            del findings["model"]
        elif failure == "zero":
            findings["tokens_out"] = 0
        elif failure == "prediction":
            findings["predictions"] = ["invalid"]
        elif failure == "location":
            findings["predictions"] = [{"title": "issue", "location": "x.c"}]
        write_json(out / "findings.json", findings)
    assert recheck_run(root)["revalidated"] == []
    assert read_json(root / "manifest.json")["tasks"][0]["status"] == "failed"


def test_recheck_refuses_active_run(tmp_path):
    root, _, _ = failed_run(tmp_path)
    with (root / ".lock").open("a") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):
            recheck_run(root)


@pytest.mark.parametrize("public_field", ["full_diff", "commit_message", "pr_description"])
def test_recheck_accepts_id_already_in_public_input(tmp_path, public_field):
    root, out, task = failed_run(tmp_path)
    data = read_json(task)
    data[public_field] = "Upstream reference to secret"
    write_json(task, data)
    (out / "trajectory.json").write_text("Reading upstream reference to secret")
    manifest = read_json(root / "manifest.json")
    manifest["tasks"][0].update(
        task_sha256=sha256_file(task), audit_events=[{"event": "private_bug_id"}],
    )
    write_json(root / "manifest.json", manifest)
    assert recheck_run(root)["revalidated"] == ["pr_review_secret"]
    proof = read_json(root / "manifest.json")["tasks"][0]["revalidation"]["public_bug_id_evidence"]
    assert proof["source"] == "public_review_input"
    assert proof["public_input_sha256"]


@pytest.mark.parametrize("public_source", ["filename", "content"])
def test_source_exception_requires_exact_task_revision(tmp_path, monkeypatch, public_source):
    repo = tmp_path / "repository"
    repo.mkdir()

    def git(*arguments):
        return subprocess.check_output(["git", "-C", str(repo), *arguments], text=True).strip()

    git("init", "-q")
    git("config", "user.name", "Test")
    git("config", "user.email", "test@example.invalid")
    (repo / "original.c").write_text("int original;\n")
    git("add", ".")
    git("commit", "-qm", "original")
    before = git("rev-parse", "HEAD")
    if public_source == "filename":
        (repo / "regress-secret.js").write_text("regression();\n")
    else:
        (repo / "reference.c").write_text("// upstream issue secret\n")
    git("add", ".")
    git("commit", "-qm", "add public reference")
    after = git("rev-parse", "HEAD")
    root, out, task = failed_run(tmp_path)
    data = read_json(task)
    data["commit_sha"] = before
    write_json(task, data)
    (out / "trajectory.json").write_text("upstream issue secret")
    assert {e["event"] for e in scan_outputs(out, data, source_repository=repo)} == {"private_bug_id"}
    # An untracked file cannot establish visibility in the archived snapshot.
    (repo / "untracked-secret.txt").write_text("secret")
    assert scan_outputs(out, data, source_repository=repo)
    data["commit_sha"] = after
    write_json(task, data)
    manifest = read_json(root / "manifest.json")
    manifest["tasks"][0].update(
        project="firefox", task_sha256=sha256_file(task), audit_events=[{"event": "private_bug_id"}],
    )
    write_json(root / "manifest.json", manifest)
    monkeypatch.setattr("secprbench.sandbox.audit.load_project", lambda _: {"clone_dir": str(repo)})
    assert recheck_run(root)["revalidated"] == ["pr_review_secret"]
    proof = read_json(root / "manifest.json")["tasks"][0]["revalidation"]["public_bug_id_evidence"]
    assert proof["source"] == "source_snapshot"
    assert proof["commit_sha"] == after


def test_public_id_does_not_exempt_other_private_data_or_denied_egress(tmp_path):
    root, out, task = failed_run(tmp_path)
    data = read_json(task)
    data.update(full_diff="upstream secret", commit_sha="a" * 40)
    write_json(task, data)
    (out / "trajectory.json").write_text('secret pr_review_secret "task_type":"benign" ' + "a" * 40)
    assert {e["event"] for e in scan_outputs(out, data)} == {
        "private_task_id", "construction_marker", "private_commit_sha",
    }
    (out / "trajectory.json").write_text("upstream secret")
    manifest = read_json(root / "manifest.json")
    manifest["tasks"][0].update(
        task_sha256=sha256_file(task),
        audit_events=[{"event": "private_bug_id"}, {"event": "denied_egress"}],
    )
    write_json(root / "manifest.json", manifest)
    assert recheck_run(root)["revalidated"] == []


def test_private_metadata_and_missing_source_do_not_grant_exception(tmp_path):
    _, out, task = failed_run(tmp_path)
    data = read_json(task)
    data["ground_truth"] = {"message": "secret"}
    data["commit_sha"] = "b" * 40
    (out / "trajectory.json").write_text("secret")
    assert {e["event"] for e in scan_outputs(out, data, source_repository=tmp_path / "missing")} == {
        "private_bug_id",
    }
