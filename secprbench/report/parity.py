"""Compare sandbox runs with frozen metrics and precisely classified prompt changes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from secprbench.harnesses.direct_review.prompts import build_user_prompt
from secprbench.io import read_json, sha256_file, write_json
from secprbench.materialize.review_input import public_review_metadata


def _user_comparison(archived: str, actual: str, task: dict[str, Any] | None) -> dict[str, Any]:
    """Allow only changes the production metadata scrubber can reconstruct.

    Before accepting a scrub, the same builder and unsanitized task must first
    reproduce the archived turn. This protects diffs, instructions, whitespace,
    and genuine upstream tags from being normalized away.
    """
    result: dict[str, Any] = {
        "first_user_equal": archived == actual,
        "first_user_compatible": archived == actual,
        "first_user_classification": "exact" if archived == actual else "unexpected_mismatch",
        "intentional_metadata_scrub": False,
    }
    if archived == actual:
        return result
    if task is None:
        result["scrub_check"] = "archived_task_unavailable"
        return result
    sanitized = {**task, **public_review_metadata(task)}
    changed = [
        name
        for name in ("commit_message", "pr_title", "pr_description")
        if sanitized.get(name, "") != (task.get(name) or "")
    ]
    for tracking in (True, False):
        if build_user_prompt(task, coverage_tracking=tracking) != archived:
            continue
        result["scrub_check"] = "archived_input_reproduced"
        if changed and build_user_prompt(sanitized, coverage_tracking=tracking) == actual:
            result.update(
                first_user_compatible=True,
                first_user_classification="intentional_metadata_scrub",
                intentional_metadata_scrub=True,
                scrubbed_metadata_fields=changed,
            )
        return result
    result["scrub_check"] = "archived_input_not_reproduced"
    return result


def _prompt_comparison(
    out: Path,
    archive: Path,
    *,
    archived_task: dict[str, Any] | None = None,
    source_hashes: dict[str, str] | None = None,
    archive_workspace: Path | None = None,
) -> dict[str, Any]:
    candidates = sorted((archive / "logs").glob("*.traj.json"))
    actual_system, actual_user = out / "system_prompt.md", out / "user_prompt.md"
    if not candidates or not actual_system.is_file() or not actual_user.is_file():
        return {"available": False, "reason": "prompt artifacts unavailable for this harness or archive"}
    for path in candidates:
        trajectory = read_json(path)
        turns = trajectory.get("turns") or []
        if trajectory.get("system_prompt") and turns and isinstance(turns[0].get("input"), str):
            expected_hash = None
            if source_hashes and archive_workspace:
                expected_hash = source_hashes.get(str(path.relative_to(archive_workspace)))
            if expected_hash and sha256_file(path) != expected_hash:
                return {
                    "available": False,
                    "reason": "archived trajectory changed since frozen capture",
                    "archived_trajectory": str(path),
                }
            system = trajectory["system_prompt"]
            workspace = (trajectory.get("metadata") or {}).get("project_directory")
            if workspace:
                system = system.replace(workspace, "/workspace")
            return {
                "available": True,
                "system_equal": system == actual_system.read_text(),
                **_user_comparison(turns[0]["input"], actual_user.read_text(), archived_task),
                "archived_trajectory": str(path),
                "archived_trajectory_hash_verified": expected_hash is not None,
            }
    return {"available": False, "reason": "no archived direct-review prompt pair"}


def _records_with_assignments(manifest: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    records = manifest.get("tasks", [])
    if not isinstance(records, list) or any(not isinstance(r, dict) for r in records):
        raise ValueError("Manifest tasks must be an array of records")
    completed = {(r["project"], r["task_id"]): r for r in records}
    if len(completed) != len(records):
        raise ValueError("Manifest contains duplicate completed task records")
    assignments = manifest.get("assignments", records)
    if not isinstance(assignments, list) or any(not isinstance(r, dict) for r in assignments):
        raise ValueError("Manifest assignments must be an array of records")
    assigned = {(r["project"], r["task_id"]): r for r in assignments}
    if len(assigned) != len(assignments) or not completed.keys() <= assigned.keys():
        raise ValueError("Completed tasks must be a subset of unique assignments")
    return [
        {**assignment, **completed[key]} if key in completed else {**assignment, "status": "pending"}
        for key, assignment in assigned.items()
    ], len(completed)


def _archived_task(snapshot: dict, identity: tuple[str, str, str], workspace: Path) -> dict | None:
    project, bug, kind = identity
    case = next((c for c in snapshot.get("cases", []) if (c["project"], c["bug_id"]) == (project, bug)), None)
    source = (case or {}).get(kind) or {}
    if not source.get("source"):
        return None
    path = workspace / source["source"]
    if not path.is_file():
        return None
    expected = source.get("sha256") or snapshot.get("source_files", {}).get(source["source"])
    # Intentional exceptions require provenance, not mutable task files found by ID.
    if not expected or sha256_file(path) != expected:
        return None
    return read_json(path)


def compare_run(run_dir: Path, frozen_snapshot: Path, archive_workspace: Path | None = None) -> dict:
    run_dir = Path(run_dir)
    archive_workspace = Path(archive_workspace) if archive_workspace is not None else None
    manifest = read_json(run_dir / "manifest.json")
    snapshot = read_json(frozen_snapshot)
    backend = {"codex": "gpt"}.get(manifest["backend"], manifest["backend"])
    archived_rows = [row for row in snapshot["results"] if row["model"] == backend]
    archived = {(row["project"], row["bug_id"], row["task_type"]): row for row in archived_rows}
    if len(archived) != len(archived_rows):
        raise ValueError("Frozen snapshot contains duplicate model/task results")
    summary = read_json(run_dir / "judge_summary.json") if (run_dir / "judge_summary.json").exists() else {}
    records, completed_count = _records_with_assignments(manifest)
    rows = []
    for record in records:
        identity = (record["project"], record["bug_id"], record["task_type"])
        previous = archived.get(identity)
        verdict = summary.get("evals", {}).get(record["task_id"], {})
        out = Path(record["output_dir"]) if record.get("output_dir") else None
        if out is not None and not out.is_absolute():
            out = run_dir / out
        judged = (
            record["status"] == "succeeded" and verdict.get("completed") is True and not verdict.get("error")
        )
        usage = record.get("usage") or {}
        row = {
            "project": identity[0],
            "bug_id": identity[1],
            "task_type": identity[2],
            "task_id": record["task_id"],
            "status": record["status"],
            "audit_events": record.get("audit_events", []),
            "new": {
                "findings": record.get("finding_count"),
                "detected": verdict.get("detected") if judged else None,
                "tokens_out": usage.get("tokens_out", usage.get("output_tokens")),
                "wall_seconds": record.get("wall_seconds"),
            },
            "archived": None,
            "prompt_parity": {
                "available": False,
                "reason": "archived source or completed output unavailable",
            },
        }
        if previous:
            old_usage = previous.get("usage") or {}
            duration = old_usage.get("duration_ms")
            row["archived"] = {
                "findings": previous.get("reports"),
                "detected": previous.get("detected"),
                "tokens_out": old_usage.get("output_tokens"),
                "wall_seconds": duration / 1000 if duration is not None else None,
                "source": previous.get("source"),
            }
            if out is not None and archive_workspace and previous.get("source"):
                row["prompt_parity"] = _prompt_comparison(
                    out,
                    archive_workspace / previous["source"],
                    archived_task=_archived_task(snapshot, identity, archive_workspace),
                    source_hashes=snapshot.get("source_files"),
                    archive_workspace=archive_workspace,
                )
            for metric in ("findings", "tokens_out", "wall_seconds"):
                new, old = row["new"][metric], row["archived"][metric]
                if new is not None and old is not None:
                    row.setdefault("delta", {})[metric] = new - old
        rows.append(row)
    prompts = [row["prompt_parity"] for row in rows if row["prompt_parity"]["available"]]
    coverage_complete = bool(rows) and len(prompts) == len(rows)
    all_compatible = all(p["system_equal"] and p["first_user_compatible"] for p in prompts)
    return {
        "backend": backend,
        "harness": manifest["harness"],
        "rows": rows,
        "assigned": len(rows),
        "completed_records": completed_count,
        "pending": sum(row["status"] == "pending" for row in rows),
        "successful": sum(row["status"] == "succeeded" for row in rows),
        "audited_violations": sum(len(row["audit_events"]) for row in rows),
        "compared_prompt_pairs": len(prompts),
        "unavailable_prompt_pairs": len(rows) - len(prompts),
        "prompt_coverage_complete": coverage_complete,
        "prompts_equal": all(p["system_equal"] and p["first_user_equal"] for p in prompts)
        if prompts
        else None,
        "intentional_metadata_scrubs": sum(p["intentional_metadata_scrub"] for p in prompts),
        "unexpected_prompt_mismatches": sum(
            not (p["system_equal"] and p["first_user_compatible"]) for p in prompts
        ),
        "prompt_contract_satisfied": coverage_complete and all_compatible if rows else None,
        "note": (
            "Raw prompts_equal covers compared_prompt_pairs only. prompt_contract_satisfied requires "
            "artifacts for every assignment, system equality after workspace substitution, and exact "
            "user equality or a precisely reconstructed intentional metadata scrub. Model outputs can "
            "vary; containment remains a separate hard gate. Archived metrics remain frozen."
        ),
    }


def register_parser(subparsers):
    parser = subparsers.add_parser("compare", help="compare sandbox output to frozen archived baseline")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--archive-workspace", type=Path)
    parser.add_argument("--output", type=Path, required=True)

    def run(args):
        result = compare_run(args.run_dir, args.snapshot, args.archive_workspace)
        write_json(args.output, result)
        return {key: value for key, value in result.items() if key != "rows"}

    parser.set_defaults(func=run)
