import subprocess
import tarfile

import pytest
from pydantic import ValidationError

from secprbench.ids import opaque_id, scan_outputs
from secprbench.materialize.review_input import write_review_input
from secprbench.materialize.snapshot import _safe_member, history_blocked, materialize_snapshot
from secprbench.schema import ReviewInput


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def test_real_snapshot_excludes_history_and_metadata_and_preserves_modes(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init")
    git(repo, "config", "user.name", "Test")
    git(repo, "config", "user.email", "test@example.invalid")
    (repo / "run.sh").write_text("#!/bin/sh\nexit 0\n")
    (repo / "run.sh").chmod(0o755)
    git(repo, "add", ".")
    git(repo, "commit", "-m", "init")
    sha = git(repo, "rev-parse", "HEAD")
    target = materialize_snapshot(repo, sha, tmp_path / "snapshot")
    assert history_blocked(target)
    assert (target / ".git").read_bytes() == b""
    assert not list(target.glob(".snapshot*"))
    assert (target / "run.sh").stat().st_mode & 0o111
    assert target.with_name("snapshot.metadata.json").is_file()
    with pytest.raises(FileExistsError):
        materialize_snapshot(repo, sha, target)
    assert git(repo, "rev-parse", "HEAD") == sha


@pytest.mark.parametrize(
    "name,link", [("../outside", None), ("/outside", None), (".git/config", None), ("link", "../../outside")]
)
def test_snapshot_rejects_escape_paths(tmp_path, name, link):
    member = tarfile.TarInfo(name)
    if link:
        member.type = tarfile.SYMTYPE
        member.linkname = link
    with pytest.raises(ValueError):
        _safe_member(member, tmp_path)


def test_whitelist_drops_private_nested_extensions(tmp_path):
    task = {
        "task_id": "pr_review_secret",
        "bug_id": "secret",
        "commit_sha": "a" * 40,
        "task_type": "buggy",
        "ground_truth": {"message": "hidden"},
        "files": [{"path": "x.c", "status": "modified", "ground_truth": "hidden"}],
    }
    review = write_review_input(task, tmp_path / "input")
    assert set(p.name for p in (tmp_path / "input").iterdir()) == {"input.json", "brief.md"}
    text = (tmp_path / "input/input.json").read_text()
    assert "secret" not in text and "hidden" not in text
    with pytest.raises(ValidationError):
        ReviewInput(**{**review.model_dump(), "bug_id": "secret"})


def test_opaque_ids_distinguish_companion_and_run():
    a = opaque_id(b"a" * 32, "case")
    b = opaque_id(b"a" * 32, "case_benign")
    assert len(a) == 12 and a != b and a != opaque_id(b"b" * 32, "case")
    with pytest.raises(ValueError):
        opaque_id(b"a", "case")


def test_output_audit_detects_private_identifiers_and_symlink(tmp_path):
    (tmp_path / "trajectory.txt").write_text("Found CVE-2026-SECRET in hidden ground truth")
    (tmp_path / "link").symlink_to("/etc/passwd")
    events = scan_outputs(tmp_path, {"bug_id": "CVE-2026-SECRET"})
    assert {x["event"] for x in events} == {"private_bug_id", "output_symlink"}


def test_native_subagent_task_type_is_not_a_benchmark_label():
    from secprbench.ids import leakage_events
    task = {'bug_id': 'private-case', 'task_id': 'private-task'}
    assert leakage_events('{"task_type":"local_agent","task_id":"random"}', task) == []
    assert 'construction_marker' in leakage_events('{"task_type":"benign"}', task)
