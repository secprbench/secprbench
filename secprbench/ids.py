"""Run-local opaque identifiers and conservative output leakage checks."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import subprocess
from functools import lru_cache
from pathlib import Path


def opaque_id(secret: bytes, task_id: str) -> str:
    if len(secret) < 16:
        raise ValueError("run secret must contain at least 128 bits")
    return hmac.new(secret, task_id.encode(), hashlib.sha256).hexdigest()[:12]


def leakage_events(text: str, task: dict) -> list[str]:
    events = []
    for field in ("bug_id", "task_id"):
        value = task.get(field)
        if value and str(value).lower() in text.lower():
            events.append(f"private_{field}")
    if re.search(
        r'(?i)(?:"task_type"\s*:\s*"(?:buggy|benign|companion)"|pr_review_|\[Benign\]|\[Merged\])', text
    ):
        events.append("construction_marker")
    for value in (task.get("fix_commit_sha"), task.get("commit_sha")):
        if value and len(value) >= 12 and value.lower() in text.lower():
            events.append("private_commit_sha")
    return sorted(set(events))


@lru_cache(maxsize=512)
def _source_bug_id(repository: str, revision: str, bug_id: str) -> dict | None:
    """Prove visibility in the exact archived tree, never the working tree/history."""
    if not re.fullmatch(r"[0-9a-fA-F]{7,40}", revision):
        return None
    try:
        resolved = subprocess.run(
            ["git", "-C", repository, "rev-parse", "--verify", f"{revision}^{{commit}}"],
            capture_output=True, text=True, timeout=30, check=True,
        ).stdout.strip()
        names = subprocess.run(
            ["git", "-C", repository, "ls-tree", "-r", "-z", "--name-only", resolved],
            capture_output=True, text=True, timeout=30, check=True,
        ).stdout.split("\0")
        path = next((name for name in names if bug_id.lower() in name.lower()), None)
        if path is None:
            match = subprocess.run(
                ["git", "-C", repository, "grep", "-i", "-F", "-l", "-z",
                 "-e", bug_id, resolved, "--"],
                capture_output=True, text=True, timeout=30, check=False,
            )
            if match.returncode != 0:
                return None
            path = match.stdout.split("\0", 1)[0].removeprefix(resolved + ":")
        return {"source": "source_snapshot", "repository": repository,
                "commit_sha": resolved, "path": path, "bug_id": bug_id}
    except (OSError, subprocess.SubprocessError):
        return None


def public_bug_id_evidence(task: dict, source_repository: str | Path | None = None) -> dict | None:
    """Only a case ID already visible in permitted input/source is public.

    Task IDs, construction markers and private commit hashes remain forbidden.
    Missing source evidence fails closed; output text cannot establish visibility.
    """
    from secprbench.materialize.review_input import build_review_input

    value = task.get("bug_id")
    if not value:
        return None
    bug_id = str(value)
    public = json.dumps(build_review_input(task).model_dump(mode="json"), sort_keys=True)
    if bug_id.lower() in public.lower():
        return {"source": "public_review_input", "bug_id": bug_id,
                "public_input_sha256": hashlib.sha256(public.encode()).hexdigest()}
    if source_repository is None:
        return None
    return _source_bug_id(str(Path(source_repository).resolve()), str(task.get("commit_sha", "")), bug_id)


def scan_outputs(
    directory: str | Path, task: dict, *, source_repository: str | Path | None = None,
) -> list[dict]:
    events = []
    for path in sorted(Path(directory).rglob("*")):
        if path.is_symlink():
            events.append({"path": str(path.relative_to(directory)), "event": "output_symlink"})
            continue
        if not path.is_file() and not path.is_dir():
            events.append({"path": str(path.relative_to(directory)), "event": "nonregular_output"})
            continue
        if path.is_file():
            if path.stat().st_size > 256 * 1024 * 1024:
                events.append({"path": str(path.relative_to(directory)), "event": "oversized_output"})
                continue
            # Stream chunks with overlap so large trajectories and split markers are checked.
            overlap = ""
            found = set(leakage_events(str(path.relative_to(directory)), task))
            with path.open("r", encoding="utf-8", errors="replace") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), ""):
                    found.update(leakage_events(overlap + chunk, task))
                    overlap = chunk[-512:]
            events.extend(
                {"path": str(path.relative_to(directory)), "event": event} for event in sorted(found)
            )
    if any(event["event"] == "private_bug_id" for event in events):
        if public_bug_id_evidence(task, source_repository) is not None:
            events = [event for event in events if event["event"] != "private_bug_id"]
    return events
