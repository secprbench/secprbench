"""Revalidate completed outputs after an auditing fix without repeating inference.

Only failed host records with a proven successful container exit are eligible.
Timeouts, denied egress, altered tasks, or invalid predictions remain failures.
"""

from __future__ import annotations

import fcntl
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import ValidationError

from secprbench.harnesses.contract import validate_predictions
from secprbench.config import load_project
from secprbench.ids import public_bug_id_evidence, scan_outputs
from secprbench.io import read_json, sha256_file, write_json
from secprbench.materialize.review_input import build_review_input


def recheck_run(run_dir: Path) -> dict:
    with (run_dir / ".lock").open("a") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _recheck_completed_run(run_dir)


def _recheck_completed_run(run_dir: Path) -> dict:
    manifest = read_json(run_dir / "manifest.json")
    changed = []
    for record in manifest["tasks"]:
        if (
            record["status"] != "failed"
            or record.get("exit_code") != 0
            or record.get("timed_out")
            or record.get("oom_killed")
        ):
            continue
        task_path, out = Path(record["task_path"]), Path(record["output_dir"])
        try:
            if sha256_file(task_path) != record["task_sha256"]:
                continue
            task = read_json(task_path)
            source_repository = None
            if record.get("project"):
                try:
                    source_repository = load_project(record["project"])["clone_dir"]
                except (OSError, ValueError, KeyError):
                    pass  # An unavailable source cannot establish a public identifier.
            events = scan_outputs(out, task, source_repository=source_repository)
            events += [event for event in record.get("audit_events", []) if event["event"] == "denied_egress"]
            if events:
                continue
            findings = validate_predictions(
                read_json(out / "findings.json"), build_review_input(task), instance_id=record["opaque_id"]
            )
            if (
                manifest["harness"] in {"direct_review", "defending", "codex"}
                and findings.get("tokens_out", 0) <= 0
            ):
                continue
        except (ValueError, TypeError, OSError, ValidationError):
            continue
        record["revalidation"] = {
            "at": datetime.now(timezone.utc).isoformat(),
            "previous_error": record.pop("error", None),
            "previous_audit_events": record.get("audit_events", []),
            "reason": "Completed container output passed current host audit and contract validation",
        }
        if any(event.get("event") == "private_bug_id" for event in record.get("audit_events", [])):
            record["revalidation"]["public_bug_id_evidence"] = public_bug_id_evidence(
                task, source_repository,
            )
        write_json(out / "findings.json", findings)
        record.update(
            status="succeeded",
            audit_events=[],
            findings_sha256=sha256_file(out / "findings.json"),
            finding_count=len(findings["predictions"]),
            usage={key: findings.get(key, 0) for key in ("tokens_in", "tokens_out", "elapsed_seconds")},
        )
        write_json(out.parent / "record.json", record)
        changed.append(record["task_id"])
    write_json(run_dir / "manifest.json", manifest)
    return {"revalidated": changed, "manifest": str(run_dir / "manifest.json")}
