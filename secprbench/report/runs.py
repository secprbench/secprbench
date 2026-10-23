"""Read host manifests and attach season/cutoff context without hiding failures."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from .aggregate import aggregate


def _read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected an object: {path}")
    return value


def _path(base: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base / path


def season_for_date(value: str | None) -> str:
    if not value:
        return "unknown"
    fixed = date.fromisoformat(str(value)[:10])
    return f"{fixed.year}H{1 if fixed.month <= 6 else 2}"


def cutoff_flag(season: str, cutoff: str | None) -> str:
    """Classify a half-year window against a declared model knowledge cutoff."""
    if cutoff is None or season == "unknown":
        return "unknown"
    if len(season) != 6 or season[4:] not in ("H1", "H2"):
        raise ValueError(f"Invalid half-year season: {season}")
    year = int(season[:4])
    start = date(year, 1 if season.endswith("H1") else 7, 1)
    end = date(year, 6, 30) if season.endswith("H1") else date(year, 12, 31)
    boundary = date.fromisoformat(cutoff)
    if end <= boundary:
        return "pre_cutoff"
    if start > boundary:
        return "post_cutoff"
    return "straddles_cutoff"


def read_run(run_dir: Path) -> list[dict[str, Any]]:
    run_dir = Path(run_dir)
    manifest = _read(run_dir / "manifest.json")
    model = str(manifest.get("backend") or manifest.get("model") or "unknown")
    summary_path = run_dir / "judge_summary.json"
    verdicts = _read(summary_path).get("evals", {}) if summary_path.exists() else {}
    if not isinstance(verdicts, dict):
        raise ValueError("Host judge summary evals must be an object")
    records = manifest.get("tasks", [])
    if not isinstance(records, list) or any(
        not isinstance(r, dict) or not r.get("task_id") or not r.get("output_dir") for r in records
    ):
        raise ValueError("Manifest tasks must be records with task_id and output_dir")
    records = [dict(record) for record in records]
    completed_keys = {(r.get("project"), r["task_id"]) for r in records}
    if len(completed_keys) != len(records):
        raise ValueError("Manifest contains duplicate task records")
    assignments = manifest.get("assignments")
    if assignments is not None:
        if not isinstance(assignments, list) or any(
            not isinstance(a, dict) or not a.get("task_id") or not a.get("project") for a in assignments
        ):
            raise ValueError("Manifest assignments must contain project and task_id")
        assigned_keys = {(a["project"], a["task_id"]) for a in assignments}
        if len(assigned_keys) != len(assignments) or not completed_keys <= assigned_keys:
            raise ValueError("Manifest tasks must be a subset of unique assignments")
        assignment_map = {(a["project"], a["task_id"]): a for a in assignments}
        records = [{**assignment_map[(r.get("project"), r["task_id"])], **r} for r in records]
        records.extend(
            {**a, "status": "pending", "usage": {}}
            for a in assignments
            if (a["project"], a["task_id"]) not in completed_keys
        )
    rows = []
    for record in records:
        out = _path(run_dir, record["output_dir"]) if record.get("output_dir") else None
        usage = {
            key: value
            for key, value in (record.get("usage") or {}).items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        }
        findings = _read(out / "findings.json") if out and (out / "findings.json").exists() else {}
        if "output_tokens" not in usage:
            usage["output_tokens"] = usage.get("tokens_out", findings.get("tokens_out", 0))
        if "input_tokens" not in usage:
            usage["input_tokens"] = usage.get("tokens_in", findings.get("tokens_in", 0))
        elapsed = usage.get(
            "elapsed_seconds",
            record.get("elapsed_seconds", record.get("wall_seconds", findings.get("elapsed_seconds"))),
        )
        if "duration_ms" not in usage and elapsed is not None:
            usage["duration_ms"] = elapsed * 1000
        predictions = findings.get("predictions", findings.get("findings"))
        if predictions is not None and not isinstance(predictions, list):
            raise ValueError(f"Invalid findings array: {out}")
        reports = len(predictions) if predictions is not None else None
        # Only the host-owned summary is authoritative: a reviewer can write any
        # filename in /out, including a forged verdict.json before judging occurs.
        verdict = verdicts.get(record["task_id"], {})
        if not isinstance(verdict, dict):
            raise ValueError("Host verdict must be an object")
        for key, path in (
            ("findings_sha256", out / "findings.json" if out else None),
            ("task_sha256", _path(run_dir, record["task_path"]) if record.get("task_path") else None),
        ):
            expected = verdict.get(key)
            if expected and (
                path is None
                or not path.is_file()
                or hashlib.sha256(path.read_bytes()).hexdigest() != expected
            ):
                raise ValueError(f"Host verdict is stale: {record['task_id']} ({key})")
        scanned = (usage.get("output_tokens") or 0) > 0
        # A failed harness may have emitted tokens, but its absent findings are not a clean negative.
        judged = bool(
            scanned
            and record.get("status") in ("succeeded", "completed", "success")
            and predictions is not None
            and verdict.get("completed") is True
            and not verdict.get("error")
        )
        detected = bool(judged and verdict.get("detected") is True)
        if scanned and reports is None:
            reports = 0
            status = "invalid_output"
        else:
            status = (
                "no_output_recorded"
                if not scanned
                else "positive_verdict"
                if detected
                else "negative_verdict"
                if judged
                else "empty_output"
                if reports == 0
                else "awaiting_judgment"
            )
        task = _read(_path(run_dir, record["task_path"])) if record.get("task_path") else {}
        fixed = record.get("fix_date") or task.get("fix_date") or task.get("fix_commit_date")
        metadata = task.get("metadata") or {}
        fixed = fixed or metadata.get("fix_date") or metadata.get("fix_commit_date")
        rows.append(
            {
                "model": model,
                "harness": manifest.get("harness"),
                "task_id": record["task_id"],
                "project": record.get("project", task.get("project", "unknown")),
                "bug_id": str(record.get("bug_id", task.get("bug_id", record["task_id"]))),
                "task_type": record.get("task_type", task.get("task_type", "unknown")),
                "season": record.get("season") or manifest.get("season") or season_for_date(fixed),
                "scanned": scanned,
                "judged": judged,
                "detected": detected,
                "reports": reports,
                "status": status,
                "run_status": record.get("status"),
                "usage": usage,
                "judge": verdict,
                "source": str(out) if out else None,
            }
        )
    return rows


def summarize_runs(run_dirs: list[Path], *, model_cutoffs: dict[str, str] | None = None) -> dict:
    rows = [row for run in run_dirs for row in read_run(run)]
    keys = [(r["model"], r["harness"], r["project"], r["task_id"]) for r in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate scans for a model/harness/task; select disjoint runs explicitly")
    groups = defaultdict(list)
    for row in rows:
        groups[(row["model"], row["harness"], row["season"], row["task_type"])].append(row)
    summaries = []
    for (model, harness, season, kind), selected in sorted(groups.items(), key=lambda pair: str(pair[0])):
        stats = aggregate(selected)
        stats.update(
            model=model,
            harness=harness,
            season=season,
            task_type=kind,
            cutoff=(model_cutoffs or {}).get(model),
            cutoff_flag=cutoff_flag(season, (model_cutoffs or {}).get(model)),
            recall=stats["detected"] / stats["assigned"] if kind == "buggy" and stats["assigned"] else None,
            failed=sum(
                r["run_status"] not in ("succeeded", "completed", "success", "pending") for r in selected
            ),
            pending=sum(r["run_status"] == "pending" for r in selected),
            invalid_output=sum(r["status"] == "invalid_output" for r in selected),
        )
        summaries.append(stats)
    return {
        "schema_version": 1,
        "policy": {
            "denominator": "All assigned manifest tasks, including failed and missing output",
            "scanned": "positive recorded output tokens",
            "benign_positive": "active-target judgment, not an adjudicated false alarm",
        },
        "groups": summaries,
        "results": rows,
    }


def summarize_seasons(
    snapshot: dict, *, case_seasons: dict[str, str] | None = None, model_cutoffs: dict[str, str] | None = None
) -> list[dict]:
    """Group a frozen archive with host-supplied project/bug -> season metadata."""
    seasons = {
        f"{c['project']}/{c['bug_id']}": c.get("season") or season_for_date(c.get("fix_date"))
        for c in snapshot["cases"]
    }
    seasons.update(case_seasons or {})
    grouped = defaultdict(list)
    for row in snapshot["results"]:
        season = seasons[f"{row['project']}/{row['bug_id']}"]
        grouped[(row["model"], season, row["task_type"])].append(row)
    result = []
    for (model, season, kind), rows in sorted(grouped.items()):
        stats = aggregate(rows)
        stats.update(
            model=model,
            season=season,
            task_type=kind,
            cutoff=(model_cutoffs or {}).get(model),
            cutoff_flag=cutoff_flag(season, (model_cutoffs or {}).get(model)),
            recall=stats["detected"] / stats["assigned"] if kind == "buggy" and stats["assigned"] else None,
        )
        result.append(stats)
    return result
