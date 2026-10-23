"""Resumable criteria-first judging for isolated runs and archived outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .auth import isolated_auth_environment
from .criteria_first import EVAL_PROMPT_VERSION, build_eval_prompt, extract_json_object, format_findings_text

SYSTEM_PROMPT = (
    "You are a strict security benchmark evaluator. Build a compact "
    "root-cause rubric first, then return one JSON verdict only."
)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected a JSON object: {path}")
    return value


def atomic_json(path: Path, value: Any) -> None:
    """Replace complete JSON, even if a run is interrupted during serialization."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(value, out, indent=2, allow_nan=False)
            out.write("\n")
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def normalize_findings(data: Any) -> list[dict[str, Any]]:
    """Convert the public prediction schema into the historical judge format."""
    if isinstance(data, dict):
        data = data.get("predictions", data.get("findings"))
    if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
        raise ValueError("Findings must be a list or an object containing predictions/findings")
    findings = []
    for item in data:
        finding = dict(item)
        if not isinstance(finding.get("location"), dict):
            finding["location"] = {
                key: finding[key] for key in ("file", "function", "start_line", "end_line") if key in finding
            }
        findings.append(finding)
    return findings


def load_findings(directory: Path, *, archival: bool = False) -> list[dict[str, Any]]:
    path = directory / "findings.json"
    if path.exists():
        return normalize_findings(json.loads(path.read_text(encoding="utf-8")))
    if archival:
        files = sorted((directory / "findings").glob("*.json"))
        if files:
            return [read_json(path) for path in files]
        reports = sorted(directory.glob("pr_review_*_report.json"))
        if len(reports) > 1:
            raise ValueError(f"Ambiguous archived report files: {directory}")
        if reports:
            return normalize_findings(read_json(reports[0]))
        return []
    raise FileNotFoundError(path)


def load_task_maps(tasks_dir: Path, task_type: str | None = None) -> tuple[dict[str, dict], dict[str, dict]]:
    tasks, references = {}, {}
    for path in sorted(tasks_dir.glob("pr_review_*.json")):
        if "index" in path.name:
            continue
        task = read_json(path)
        bug = str(task.get("bug_id", ""))
        if not bug:
            continue
        prior = tasks.get(bug)
        preferred = task.get("task_type") == task_type if task_type else task.get("task_type") != "benign"
        if prior is None or preferred:
            tasks[bug] = task
        gt = task.get("ground_truth") or {}
        if any(gt.get(key) for key in ("root_cause", "bug_type", "findings")) and (
            bug not in references or task.get("task_type") != "benign"
        ):
            references[bug] = gt
    return tasks, references


def normalize_verdict(bug_id: str, result: dict[str, Any], findings_count: int) -> dict[str, Any]:
    # Python bool("false") is True; malformed model output must never become a hit.
    if type(result.get("detected")) is not bool:
        raise ValueError("detected must be a JSON boolean")
    if result.get("bug_id") not in (None, "", bug_id):
        raise ValueError("Judge returned a different bug identity")
    for key in ("all_criteria_met", "fix_or_mitigation_present", "finding_contradicts_active_vulnerability"):
        if key in result and result[key] is not None and type(result[key]) is not bool:
            raise ValueError(f"{key} must be a JSON boolean")
    if result["detected"] and (
        result.get("current_code_support") == "fixed"
        or result.get("fix_or_mitigation_present") is True
        or result.get("finding_contradicts_active_vulnerability") is True
    ):
        raise ValueError("Positive verdict contradicts its own active-vulnerability evidence")
    criteria = result.get("criteria") or []
    if not isinstance(criteria, list):
        raise TypeError("criteria must be a JSON array")
    try:
        score = max(0, min(100, int(float(result.get("match_score") or 0))))
    except (TypeError, ValueError, OverflowError):
        raise ValueError("match_score must be a finite number") from None
    return {
        "bug_id": bug_id,
        "detected": result["detected"],
        "confidence": str(result.get("confidence", "LOW")),
        "match_score": score,
        "criteria": [str(item) for item in criteria[:6]],
        "all_criteria_met": result.get("all_criteria_met", False),
        "current_code_support": str(result.get("current_code_support", "unknown")),
        "fix_or_mitigation_present": result.get("fix_or_mitigation_present"),
        "finding_contradicts_active_vulnerability": result.get(
            "finding_contradicts_active_vulnerability", False
        ),
        **{
            key: str(result.get(key, "")) for key in ("reasoning", "findings_summary", "ground_truth_summary")
        },
        "verification_timestamp": datetime.now(timezone.utc).isoformat(),
        "num_findings": findings_count,
        "verification_method": "criteria-first-agent",
        "prompt_version": EVAL_PROMPT_VERSION,
        "completed": True,
        "error": False,
    }


def caw_completion(
    prompt: str,
    *,
    model: str,
    reasoning_effort: str | None = "high",
    claude_version: str | None = "2.1.283",
    paper_tools: bool = False,
    no_web: bool = True,
    workspace: Path | None = None,
    backend: str | None = None,
) -> str:
    """Run caw in a child process: its Claude provider ignores a cwd keyword."""
    if paper_tools and (workspace is None or not workspace.is_dir()):
        raise ValueError("Tool-enabled judging requires an explicit evaluated snapshot workspace")
    payload = {"prompt": prompt, "model": model, "paper_tools": paper_tools, "no_web": no_web,
               "reasoning_effort": reasoning_effort, "claude_version": claude_version}
    env = dict(os.environ)
    if backend:
        from ..config import load_backend

        spec = load_backend(backend)
        if spec.name == "codex":
            raise ValueError("The criteria-first Claude CLI judge requires a Claude-compatible backend")
        env.update(spec.environment())
    package_root = str(Path(__file__).resolve().parents[2])
    env["PYTHONPATH"] = os.pathsep.join(filter(None, (package_root, env.get("PYTHONPATH"))))
    with tempfile.TemporaryDirectory(prefix="secprbench-judge-") as isolated:
        env = isolated_auth_environment(env, Path(isolated))
        proc = subprocess.run(
            [sys.executable, "-m", "secprbench.judge.worker"],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            cwd=str(workspace.resolve()) if paper_tools else isolated,
            env=env,
            timeout=1200,
            check=False,
        )
    if proc.returncode:
        raise RuntimeError(f"Judge subprocess failed ({proc.returncode}): {proc.stderr[-2000:]}")
    return str(json.loads(proc.stdout)["response"])


def judge_task(
    task: dict[str, Any],
    reference: dict[str, Any],
    findings: list[dict[str, Any]],
    output_dir: Path,
    *,
    model: str = "claude-opus-5-5",
    reasoning_effort: str | None = "high",
    claude_version: str | None = "2.1.283",
    max_attempts: int = 3,
    max_diff_chars: int = 30000,
    paper_tools: bool = False,
    no_web: bool = True,
    workspace: Path | None = None,
    force: bool = False,
    backend: str | None = None,
    complete: Callable[..., str] | None = None,
) -> dict[str, Any]:
    if max_attempts < 1 or max_diff_chars < 1:
        raise ValueError("Judge attempts and diff budget must be positive")
    if reasoning_effort not in (None, "low", "medium", "high", "max"):
        raise ValueError("Invalid judge reasoning effort")
    bug_id = str(task["bug_id"])
    prompt = build_eval_prompt(bug_id, task, reference, format_findings_text(findings), max_diff_chars)
    signature = hashlib.sha256(
        json.dumps(
            {
                "prompt": prompt,
                "model": model,
                "reasoning_effort": reasoning_effort,
                "claude_version": claude_version,
                "paper_tools": paper_tools,
                "backend": backend,
                "no_web": no_web,
                "workspace": str(workspace) if workspace else None,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    verdict_path = output_dir / "verdict.json"
    if verdict_path.exists() and not force:
        old = read_json(verdict_path)
        if old.get("completed") and not old.get("error") and old.get("input_sha256") == signature:
            return old
    logs = output_dir / "judge_logs"
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "bench_eval_verifier_prompt.txt").write_text(prompt, encoding="utf-8")
    errors = []
    result = None
    if not findings:
        result = normalize_verdict(
            bug_id, {"detected": False, "reasoning": "No vulnerabilities reported by the scanner."}, 0
        )
        result["verification_method"] = "empty-output"
    for attempt in range(1, max_attempts + 1) if findings else ():
        response = ""
        try:
            response = (complete or caw_completion)(
                prompt,
                model=model,
                reasoning_effort=reasoning_effort,
                claude_version=claude_version,
                paper_tools=paper_tools,
                no_web=no_web,
                workspace=workspace,
                backend=backend,
            )
            result = normalize_verdict(bug_id, extract_json_object(response), len(findings))
        except Exception as exc:  # noqa: BLE001 - persist third-party/model failures per task
            errors.append({"attempt": attempt, "error": str(exc)})
            atomic_json(logs / f"bench_eval_verifier_attempt_{attempt}.error.json", errors[-1])
        finally:
            (logs / f"bench_eval_verifier_attempt_{attempt}.txt").write_text(response, encoding="utf-8")
        if result is not None:
            break
    if result is None:
        result = {
            "bug_id": bug_id,
            "detected": False,
            "completed": False,
            "error": True,
            "num_findings": len(findings),
            "prompt_version": EVAL_PROMPT_VERSION,
            "verification_errors": errors,
            "reasoning": f"Evaluation failed after {len(errors)} attempts",
        }
    result.update(
        input_sha256=signature, eval_model=model, eval_backend=backend, paper_tools=paper_tools, no_web=no_web,
        reasoning_effort=reasoning_effort, claude_version=claude_version
    )
    atomic_json(verdict_path, result)
    return result


def judge_run(run_dir: Path, *, tasks_dir: Path | None = None, **options: Any) -> dict[str, Any]:
    manifest = read_json(run_dir / "manifest.json")
    summary = {"prompt_version": EVAL_PROMPT_VERSION, "evals": {}, "errors": []}
    for record in manifest.get("tasks", []):
        if record.get("status") not in ("succeeded", "completed", "success"):
            continue
        task_id = record["task_id"]
        try:
            task_path = Path(record["task_path"])
            if not task_path.is_absolute():
                task_path = run_dir / task_path
            if (
                record.get("task_sha256")
                and hashlib.sha256(task_path.read_bytes()).hexdigest() != record["task_sha256"]
            ):
                raise ValueError("Task changed after review; refusing to judge a different revision")
            task = read_json(task_path)
            _, refs = load_task_maps(tasks_dir or task_path.parent)
            reference = refs.get(str(task["bug_id"]))
            if not reference:
                raise ValueError("Missing detailed ground-truth reference")
            out = Path(record["output_dir"])
            if not out.is_absolute():
                out = run_dir / out
            findings_path = out / "findings.json"
            if findings_path.is_symlink():
                raise ValueError("Findings must not be a symlink")
            if (
                record.get("findings_sha256")
                and hashlib.sha256(findings_path.read_bytes()).hexdigest() != record["findings_sha256"]
            ):
                raise ValueError("Findings changed after review; rerun the review or use an archival copy")
            opts = dict(options)
            if record.get("workspace") and opts.get("workspace") is None:
                opts["workspace"] = Path(record["workspace"])
            verdict = judge_task(task, reference, load_findings(out), out, **opts)
            verdict = {
                **verdict,
                "task_sha256": hashlib.sha256(task_path.read_bytes()).hexdigest(),
                "findings_sha256": hashlib.sha256(findings_path.read_bytes()).hexdigest(),
            }
            atomic_json(out / "verdict.json", verdict)
            summary["evals"][task_id] = verdict
        except Exception as exc:  # noqa: BLE001 - persist third-party/model failures per task
            summary["errors"].append({"task_id": task_id, "error": str(exc)})
        atomic_json(run_dir / "judge_summary.json", summary)
    atomic_json(run_dir / "judge_summary.json", summary)
    return summary


def judge_archive(
    output_dir: Path, tasks_dir: Path, *, task_type: str | None = None, **options: Any
) -> dict[str, Any]:
    tasks, refs = load_task_maps(tasks_dir, task_type)
    summary = {"evals": {}, "prompt_version": EVAL_PROMPT_VERSION, "errors": []}
    for directory in sorted(output_dir.glob("bug_*")):
        bug = directory.name[4:]
        try:
            findings = load_findings(directory, archival=True)
            if not findings:
                continue  # Preserve the paper's skipped-empty accounting.
            summary["evals"][bug] = judge_task(tasks[bug], refs[bug], findings, directory, **options)
        except Exception as exc:  # noqa: BLE001 - persist third-party/model failures per task
            summary["errors"].append({"bug_id": bug, "error": str(exc)})
        atomic_json(output_dir / "bench_eval_summary.json", summary)
    atomic_json(output_dir / "bench_eval_summary.json", summary)
    return summary


def register_parser(subparsers: Any) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "judge", help="Judge saved findings with the criteria-first reference rubric"
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--run-dir", type=Path)
    target.add_argument("--output-dir", type=Path, help="Archived bug_* output layout")
    parser.add_argument("--tasks-dir", type=Path)
    parser.add_argument("--task-type", choices=("buggy", "benign"))
    parser.add_argument("--config", type=Path, help="Judge YAML overrides (defaults to configs/judge.yaml)")
    parser.add_argument("--model")
    parser.add_argument("--reasoning-effort", choices=("low", "medium", "high", "max"))
    parser.add_argument("--claude-version", help="Required judge CLI version; recorded in verdicts")
    parser.add_argument(
        "--backend", help="Optional Claude-compatible backend YAML/name for an explicitly different judge"
    )
    parser.add_argument("--max-attempts", type=int)
    parser.add_argument("--max-diff-chars", type=int)
    parser.add_argument(
        "--paper-tools",
        action="store_true",
        default=None,
        help="Restore the historical tool-enabled evaluator",
    )
    parser.add_argument("--allow-web", action="store_true", default=None)
    parser.add_argument("--workspace", type=Path, help="Evaluated snapshot for paper-tools mode")
    parser.add_argument("--force", action="store_true")
    parser.set_defaults(func=main)
    return parser


def main(args: argparse.Namespace) -> int:
    if args.output_dir and not args.tasks_dir:
        raise ValueError("--tasks-dir is required with --output-dir")
    from ..config import config_root, load_yaml

    options = {
        "model": "claude-opus-5-5",
        "reasoning_effort": "high",
        "claude_version": "2.1.283",
        "max_attempts": 3,
        "max_diff_chars": 30000,
        "paper_tools": False,
        "no_web": True,
    }
    config_path = args.config or config_root() / "judge.yaml"
    if args.config or config_path.exists():
        config = load_yaml(config_path)
        version = config.pop("prompt_version", EVAL_PROMPT_VERSION)
        if version != EVAL_PROMPT_VERSION:
            raise ValueError(f"Unsupported judge prompt version: {version}")
        unknown = set(config) - set(options)
        if unknown:
            raise ValueError(f"Unknown judge configuration keys: {sorted(unknown)}")
        options.update(config)
    for key in ("model", "reasoning_effort", "claude_version", "max_attempts", "max_diff_chars", "paper_tools"):
        value = getattr(args, key)
        if value is not None:
            options[key] = value
    if args.allow_web is not None:
        options["no_web"] = not args.allow_web
    if not options["no_web"] and not options["paper_tools"]:
        raise ValueError("Web access requires --paper-tools")
    if args.backend:
        from ..config import load_backend

        judge_backend = load_backend(args.backend)
        if args.model is None:
            options["model"] = judge_backend.model
    options.update(workspace=args.workspace, force=args.force, backend=args.backend)
    if args.run_dir:
        summary = judge_run(args.run_dir, tasks_dir=args.tasks_dir, **options)
    else:
        summary = judge_archive(args.output_dir, args.tasks_dir, task_type=args.task_type, **options)
    print(json.dumps({"evaluated": len(summary["evals"]), "errors": summary["errors"]}, indent=2))
    return int(bool(summary["errors"]) or any(item.get("error") for item in summary["evals"].values()))
