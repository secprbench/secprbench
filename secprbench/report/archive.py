"""Read the historical paper outputs without invoking models.

Ports the paper freeze accounting; no original package is imported.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

MODELS = {
    "opus": ("Claude Opus 5", "base_recall_opus"),
    "grok": ("Grok 4.6", "base_recall_grok"),
    "glm": ("GLM 5.3", "base_recall_glm"),
    "minimax": ("MiniMax M3", "base_recall_minimax"),
    "gpt": ("GPT-5.6 sol (xhigh)", "base_recall_codex_gpt_5_6_sol_xhigh"),
}


def freeze_archive(
    workspace: Path, *, roster_path: Path | None = None, captured_at: str | None = None
) -> dict:
    root = Path(workspace).resolve()
    sources, errors = {}, []

    def read(path, optional=True):
        try:
            raw = path.read_bytes()
        except FileNotFoundError:
            if not optional:
                raise
            return {}
        sources[str(path.relative_to(root))] = hashlib.sha256(raw).hexdigest()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            errors.append(str(path.relative_to(root)))
            return {}

    roster_path = Path(roster_path) if roster_path else root / "tmp/anth_opus_verified_tasks.tsv"
    raw_roster = roster_path.read_bytes()
    sources[str(roster_path.relative_to(root))] = hashlib.sha256(raw_roster).hexdigest()
    roster = [
        line.split("\t")
        for line in raw_roster.decode().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    if not roster or len(roster) != len({(p, b) for p, b, _ in roster}):
        raise ValueError("Roster must be nonempty and contain unique project/bug pairs")
    started = datetime.now(timezone.utc).isoformat()
    cases = []
    for project, bug, route in roster:
        case = {
            "project": project,
            "bug_id": bug,
            "verification_status": route,
            "verification_route": "human" if route in {"human_cat1", "human_verified"} else "mechanical",
        }
        for kind, suffix in [("buggy", ""), ("benign", "_benign")]:
            path = root / f"cgsa_datasets/{project}/pr_tasks/pr_review_{bug}{suffix}.json"
            task = read(path, optional=False)
            files = task["files"]
            diff = "".join(f.get("diff", "") for f in files)
            changed = sum(
                line[:1] in {"+", "-"} and not line.startswith(("+++ ", "--- ")) for line in diff.splitlines()
            )
            case[kind] = {
                "source": str(path.relative_to(root)),
                "sha256": sources[str(path.relative_to(root))],
                "commit_sha": task.get("commit_sha"),
                "intro_commit_sha": task.get("intro_commit_sha") or task.get("commit_sha"),
                "diff_sha256": hashlib.sha256(diff.encode()).hexdigest(),
                "files": len(files),
                "lines": changed,
            }
        cases.append(case)

    results, runs = [], []
    for model, (label, arm) in MODELS.items():
        for kind in ("buggy", "benign"):
            for project in sorted({c["project"] for c in cases}):
                if kind == "buggy":
                    paths = [root / f"bench/pr_bench_{project}/bench_{arm}"]
                else:
                    token = "codex" if model == "gpt" else model
                    base = root / f"tmp/benign_verified_bench/bench/pr_bench_{project}"
                    paths = sorted(p for p in base.glob(f"bench_benign_verified_{token}*") if p.is_dir())
                paths = [p for p in paths if p.is_dir()]
                evaluations = {}
                for path in paths:
                    evaluation = read(path / "bench_eval_summary.json")
                    evaluations[path] = evaluation.get("evals") or {}
                    config = read(path / "summary.json").get("config") or {}
                    runs.append(
                        {
                            "model": model,
                            "task_type": kind,
                            "project": project,
                            "source": str(path.relative_to(root)),
                            "eval_model": evaluation.get("eval_model"),
                            "config": {
                                k: config.get(k)
                                for k in (
                                    "model",
                                    "no_web",
                                    "max_scan_turns",
                                    "scan_pack",
                                    "coverage",
                                    "task_type",
                                    "scanner",
                                    "prompt_pack",
                                    "stage2_timeout_seconds",
                                    "codex_args",
                                )
                            },
                        }
                    )
                for case in (c for c in cases if c["project"] == project):
                    bug = case["bug_id"]
                    candidates = [p for p in paths if (p / f"bug_{bug}").is_dir()]
                    # Disjoint project shards are expected. Refuse to silently
                    # select or combine two scans if a merge creates duplicates.
                    if len(candidates) > 1:
                        raise ValueError(
                            f"Duplicate archived scans: {(model, kind, project, bug, candidates)}"
                        )
                    row = {
                        "model": model,
                        "task_type": kind,
                        "project": project,
                        "bug_id": bug,
                        "scanned": False,
                        "judged": False,
                        "detected": False,
                        "reports": None,
                        "finding_files": 0,
                        "usage": {},
                        "status": "missing",
                        "source": None,
                    }
                    if not candidates:
                        results.append(row)
                        continue
                    run = candidates[0]
                    bug_dir = run / f"bug_{bug}"
                    row["source"] = str(bug_dir.relative_to(root))
                    usage_files = (
                        sorted((bug_dir / "logs").glob("codex_stage2_usage.json"))
                        if model == "gpt"
                        else sorted((bug_dir / "logs").glob("*.traj.json"))
                    )
                    usage = {}
                    sessions = []
                    for path in usage_files:
                        d = read(path)
                        u = d.get("usage") or {} if model == "gpt" else d.get("total_usage") or {}
                        values = {k: u.get(k) for k in ("input_tokens", "output_tokens")}
                        if model == "gpt":
                            cached = u.get("cached_input_tokens") or 0
                            values["input_tokens"] = (u.get("input_tokens") or 0) - cached
                            values["cache_read_tokens"] = cached
                            values["cache_write_tokens"] = u.get("cache_write_input_tokens")
                            values["cost_usd"] = d.get("cost_usd")
                            inv = read(path.with_name("codex_stage2_invocation.json"))
                            elapsed = inv.get("elapsed_seconds")
                            values["duration_ms"] = elapsed * 1000 if elapsed is not None else None
                            row["invocation_ok"] = inv.get("ok")
                        else:
                            values.update(
                                {k: u.get(k) for k in ("cache_read_tokens", "cache_write_tokens", "cost_usd")}
                            )
                            values["duration_ms"] = d.get("duration_ms")
                        for key, value in values.items():
                            if value is not None:
                                usage[key] = usage.get(key, 0) + value
                        sessions.append(
                            {
                                "source": str(path.relative_to(root)),
                                "model": d.get("model"),
                                "completed_at": d.get("completed_at"),
                                "usage": values,
                            }
                        )
                    row["usage"] = usage
                    row["usage_sessions"] = sessions
                    row["scanned"] = (usage.get("output_tokens") or 0) > 0
                    findings = sorted((bug_dir / "findings").glob("*.json"))
                    row["finding_files"] = len(findings)
                    suffix = "_benign" if kind == "benign" else ""
                    report_path = bug_dir / f"pr_review_{bug}{suffix}_report.json"
                    report = read(report_path)
                    if isinstance(report.get("findings"), list):
                        row["reports"] = len(report["findings"])
                        row["report_source"] = "final_report"
                        row["scan_report_status"] = report.get("status")
                    else:
                        row["reports"] = len(findings)
                        row["report_source"] = "finding_files"
                    for path in findings:
                        read(path)
                    e = evaluations[run].get(bug) or {}
                    row["judge"] = {
                        k: e.get(k)
                        for k in (
                            "completed",
                            "error",
                            "detected",
                            "num_findings",
                            "current_code_support",
                            "fix_or_mitigation_present",
                            "verification_timestamp",
                            "reasoning",
                        )
                    }
                    row["judged"] = bool(
                        row["scanned"] and e and e.get("completed", True) and not e.get("error")
                    )
                    row["detected"] = bool(row["judged"] and e.get("detected"))
                    if not row["scanned"]:
                        row["status"] = "no_output_recorded"
                    elif row["detected"]:
                        row["status"] = "positive_verdict"
                    elif row["judged"]:
                        row["status"] = "negative_verdict"
                    elif row["reports"] == 0:
                        row["status"] = "empty_output"
                    else:
                        row["status"] = "awaiting_judgment"
                    results.append(row)

    snapshot = {
        "schema_version": 1,
        "capture_started_at": started,
        "captured_at": captured_at or datetime.now(timezone.utc).isoformat(),
        "description": "Baseline results on 160 validated buggy/benign pairs, with incomplete runs explicit.",
        "models": {k: v[0] for k, v in MODELS.items()},
        "cases": cases,
        "results": results,
        "runs": runs,
        "source_files": sources,
        "unreadable_json": errors,
        "policy": {
            "scanned": "positive recorded scanner output tokens",
            "judged": "non-error completed verdict attached to a scanned task",
            "recall_denominator": len(cases),
            "report_count": "final report, falling back to finding files if absent",
            "benign_positive": "active-target judgment; not an adjudicated false alarm",
            "cost_scope": "recorded scan sessions; excludes judging and construction",
        },
    }
    if errors:
        raise ValueError(f"Unreadable archive JSON: {errors}")
    return snapshot


def audit_sources(workspace: Path, snapshot: dict) -> dict:
    """Report source drift without silently substituting new runs for frozen ones."""
    changed, missing = [], []
    for name, expected in snapshot.get("source_files", {}).items():
        path = Path(workspace) / name
        try:
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            missing.append(name)
            continue
        if actual != expected:
            changed.append(name)
    return {
        "checked": len(snapshot.get("source_files", {})),
        "changed": changed,
        "missing": missing,
        "matched": len(snapshot.get("source_files", {})) - len(changed) - len(missing),
    }
