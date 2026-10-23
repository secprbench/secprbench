"""Command-line interface for evaluating scanners on the released SecPRBench cohort."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _parser() -> argparse.ArgumentParser:
    from secprbench.config import work_root

    parser = argparse.ArgumentParser(prog="secprbench", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    from secprbench.judge.runner import register_parser as judge
    from secprbench.report.tables import register_parser as report
    from secprbench.report.parity import register_parser as compare

    for register in (judge, report, compare):
        register(sub)
    audit = sub.add_parser("audit", help="revalidate completed failed reviews under current auditing rules")
    audit.add_argument("--run-dir", type=Path, required=True)
    audit.set_defaults(func=_audit)
    prepare = sub.add_parser("prepare", help="Clone a project and check a task revision without running models")
    prepare.add_argument("--project", required=True)
    prepare.add_argument("--task", type=Path, help="Check availability of this task's pinned commit")
    prepare.set_defaults(func=_prepare)
    materialize = sub.add_parser("materialize", help="prepare a history-free snapshot and public task input")
    materialize.add_argument("--task", type=Path, required=True)
    materialize.add_argument("--project", required=True)
    materialize.add_argument("--output", type=Path, required=True)
    materialize.set_defaults(func=_materialize)
    run = sub.add_parser("run", help="run a roster in isolated reviewer containers")
    run.add_argument("--roster", type=Path, default=Path("data/roster.json"))
    run.add_argument("--data-root", type=Path, default=Path("data"))
    run.add_argument("--backend", required=True)
    run.add_argument("--harness", default="direct_review")
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--work-root", type=Path, default=work_root())
    run.add_argument("--concurrency", type=int, default=8)
    run.add_argument("--limit", type=int)
    run.add_argument("--projects", nargs="+")
    run.add_argument("--task-type", choices=["both", "buggy", "benign"], default="both")
    run.add_argument("--timeout", type=int)
    run.add_argument("--keep-snapshot", action="store_true")
    run.set_defaults(func=_run)
    check = sub.add_parser("check", help="probe Docker containment and configured API reachability")
    check.add_argument("--backend")
    check.add_argument("--harness", default="direct_review")
    check.add_argument("--work-root", type=Path, default=work_root())
    check.add_argument("--live-task", type=Path, help="Also run one paid harness review of this task JSON")
    check.add_argument("--project", help="Project for --live-task")
    check.set_defaults(func=_check)
    harness = sub.add_parser("harness")
    actions = harness.add_subparsers(dest="action", required=True)
    scaffold = actions.add_parser("scaffold")
    scaffold.add_argument("name")
    scaffold.add_argument("--output", type=Path, default=Path("harnesses"))
    scaffold.set_defaults(func=_scaffold)
    image = sub.add_parser("build-images")
    image.add_argument("--repository", type=Path, default=Path(__file__).resolve().parent.parent)
    image.add_argument("--work-root", type=Path, default=work_root())
    image.add_argument(
        "--claude-binary", type=Path, default=Path.home() / ".local/share/claude/versions/2.1.283"
    )
    image.set_defaults(func=_build)
    return parser


def _audit(args):
    from secprbench.sandbox.audit import recheck_run

    return recheck_run(args.run_dir)


def _prepare(args):
    from secprbench.materialize.prepare import prepare_project

    return prepare_project(args.project, args.task)


def _materialize(args):
    from secprbench.config import load_project
    from secprbench.io import read_json
    from secprbench.materialize.review_input import write_review_input
    from secprbench.materialize.snapshot import materialize_snapshot

    task = read_json(args.task)
    write_review_input(task, args.output / "input")
    materialize_snapshot(
        load_project(args.project)["clone_dir"], task["commit_sha"], args.output / "workspace"
    )
    return {"output": str(args.output.resolve())}


def _run(args):
    from secprbench.sandbox.runner import run_roster

    result = run_roster(
        roster=args.roster,
        data_root=args.data_root,
        backend_name=args.backend,
        harness_name=args.harness,
        run_dir=args.output,
        work_root=args.work_root,
        concurrency=args.concurrency,
        limit=args.limit,
        projects=args.projects,
        timeout=args.timeout,
        keep_snapshot=args.keep_snapshot,
        task_type=args.task_type,
    )
    failed = sum(row["status"] != "succeeded" for row in result["tasks"])
    print(
        json.dumps(
            {"tasks": len(result["tasks"]), "failed": failed, "manifest": str(args.output / "manifest.json")}
        )
    )
    return 1 if failed else 0


def _check(args):
    if args.live_task and (not args.backend or not args.project):
        raise ValueError("--live-task requires --backend and --project")
    if args.backend:
        from secprbench.sandbox.check import check_sandbox

        result = check_sandbox(args.backend, args.harness, args.work_root)
        if args.live_task:
            if not args.project:
                raise ValueError("--live-task requires --project")
            from secprbench.io import read_json, write_json, sha256_file
            from secprbench.sandbox.runner import run_roster

            task = read_json(args.live_task)
            kind = task.get("task_type", "buggy")
            roster = Path(result["report"]).parent / "smoke-roster.json"
            write_json(
                roster,
                {
                    "name": "harness-smoke",
                    "entries": [
                        {
                            "project": args.project,
                            "bug_id": task["bug_id"],
                            kind: {
                                "path": str(args.live_task.resolve()),
                                "sha256": sha256_file(args.live_task),
                            },
                        }
                    ],
                },
            )
            live = run_roster(
                roster=roster,
                data_root=Path("."),
                backend_name=args.backend,
                harness_name=args.harness,
                run_dir=roster.parent / "live",
                work_root=args.work_root,
                concurrency=1,
                task_type=kind,
            )
            result["live"] = {
                "manifest": str(roster.parent / "live/manifest.json"),
                "passed": all(row["status"] == "succeeded" for row in live["tasks"]),
            }
            result["passed"] = result["passed"] and result["live"]["passed"]
            write_json(result["report"], result)
    else:
        raise ValueError("check requires --backend")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


def _scaffold(args):
    from secprbench.harnesses.contract import scaffold

    return {"directory": str(scaffold(args.name, args.output))}


def _build(args):
    from secprbench.sandbox.build import build_images

    return build_images(args.repository, args.work_root, args.claude_binary)


def main(argv=None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        handler = getattr(args, "func", None) or getattr(args, "handler", None)
        if handler is None:
            parser.error("command does not have a handler")
        result = handler(args)
        if isinstance(result, int):
            return result
        if result is not None:
            print(json.dumps(result, indent=2, default=str))
        return 0
    except (ValueError, FileNotFoundError, FileExistsError) as exc:
        parser.exit(2, f"secprbench: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
