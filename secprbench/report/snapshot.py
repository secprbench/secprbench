"""Adapt current frozen evidence to the existing report accounting contract."""

from __future__ import annotations


def normalize_snapshot(snapshot: dict) -> dict:
    if "cases" in snapshot and "results" in snapshot:
        return snapshot
    if snapshot.get("schema_version") != 2 or not all(k in snapshot for k in ("tasks", "records", "labels")):
        raise ValueError("Unsupported frozen snapshot: expected historical cases/results or current schema 2")
    cases = []
    for key, task in snapshot["tasks"].items():
        if key != f"{task['project']}/{task['bug_id']}":
            raise ValueError(f"Task identity mismatch: {key}")
        cases.append({
            "project": task["project"], "bug_id": task["bug_id"],
            "season": task.get("season"), "fix_date": task.get("fix_date"),
            "verification_route": task["admission"],
            "buggy": {"files": task["files"], "lines": task["lines"],
                      "intro_commit_sha": task["intro_commit_sha"]},
            "benign": {"files": task["companion_files"], "lines": task["companion_lines"]},
        })
    records = []
    for record in snapshot["records"]:
        key, model, kind = record["task"], record["key"], record["task_type"]
        if key not in snapshot["tasks"] or model not in snapshot["labels"] or kind not in ("buggy", "benign"):
            raise ValueError(f"Unknown result assignment: {model}/{key}/{kind}")
        task = snapshot["tasks"][key]
        if record.get("project") != task["project"]:
            raise ValueError(f"Result project mismatch: {key}")
        if any(type(record.get(field)) is not bool for field in ("scanned", "judged", "detected")):
            raise ValueError(f"Result accounting flags must be booleans: {key}")
        reports = record.get("n_findings")
        if reports is not None and (type(reports) is not int or reports < 0):
            raise ValueError(f"Invalid finding count: {key}")
        status = (
            "no_output_recorded" if not record["scanned"] else
            "invalid_output" if reports is None else
            "positive_verdict" if record["detected"] else
            "negative_verdict" if record["judged"] else
            "empty_output" if reports == 0 else "awaiting_judgment"
        )
        records.append({**record, "model": model, "bug_id": task["bug_id"],
                        "reports": reports or 0, "status": status,
                        "judge": record.get("judge") or {}, "usage": record.get("usage") or {}})
    return {**snapshot, "cases": cases, "results": records, "models": snapshot["labels"]}
