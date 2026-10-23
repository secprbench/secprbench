"""Paper table parity and command-line report exports."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any

from ..judge.runner import atomic_json
from .aggregate import LABELS, LANG, NAMES, ORDER, derive, derive_comparison
from .archive import audit_sources, freeze_archive
from .runs import summarize_runs, summarize_seasons
from .snapshot import normalize_snapshot


def row(*cells):
    return " & ".join(map(str, cells)) + r" \\" + "\n"


def write_paper_tables(snapshot: dict, output_dir: Path) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    def write(name, content):
        (output_dir / name).write_text(content, encoding="utf-8")

    stats = derive(snapshot)
    comparison = derive_comparison(snapshot, stats)
    cases, results = snapshot["cases"], snapshot["results"]
    n = len(cases)
    main_text, cost_text, fixed_text = "", "", ""
    for model in ORDER:
        a = stats["models"][model]["buggy"]
        if a["scanned"] != n or a["unjudged_findings"]:
            raise ValueError(f"Paper table requires complete buggy scans: {model}")
        main_text += row(LABELS[model], a["detected"], f"{100 * a['detected'] / n:.1f}\\%", a["empty"])
        cost_text += row(
            LABELS[model],
            f"{a['reports_per_scan']:.2f}",
            f"{a['mean_output_tokens'] / 1000:.1f}",
            f"{a['median_minutes']:.1f}",
        )
        b = stats["models"][model]["benign"]
        # Compare complete paired evaluations; partial runs remain in the data.
        if b["scanned"] == n and not b["unjudged_findings"]:
            fixed_text += row(
                LABELS[model],
                f"{b['any_report']}/{n}",
                b["reports"],
                f"{b['reports_per_scan']:.2f}",
                b["detected"],
            )
    write("baseline_main_rows.tex", main_text)
    write("baseline_cost_rows.tex", cost_text)
    write("baseline_fixed_rows.tex", fixed_text)
    write(
        "model_agreement_rows.tex",
        row("Tasks", *(comparison["models_detecting_target"][str(i)] for i in range(len(ORDER) + 1))),
    )
    ratios = comparison["benign_to_buggy_report_ratio"].values()
    comparison_macros = {
        "numAnyModelDetected": comparison["any_model_detected"],
        "numSharedMisses": len(comparison["shared_miss_cases"]),
        "numAdditionalDetections": len(comparison["additional_cases_beyond_highest_recall_model"]),
        "opusNonemptyMisses": comparison["misses_by_model"]["opus"]["nonempty"],
        "gptNonemptyMisses": comparison["misses_by_model"]["gpt"]["nonempty"],
        "gptMisses": comparison["misses_by_model"]["gpt"]["missed"],
        "benignReportRatioLow": f"{100 * min(ratios):.1f}\\%",
        "benignReportRatioHigh": f"{100 * max(ratios):.1f}\\%",
        "glmOpusTokenRatio": f"{comparison['glm_to_opus_usage_ratio']['mean_output_tokens']:.1f}",
        "glmOpusTimeRatio": f"{comparison['glm_to_opus_usage_ratio']['median_duration']:.1f}",
    }
    write(
        "comparison_macros.tex",
        "".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in comparison_macros.items()),
    )
    (output_dir / "comparison_analysis.json").write_text(json.dumps(comparison, indent=2) + "\n")

    dataset_text, verification_text, project_text = "", "", ""
    for project in sorted(NAMES):
        selected = [c for c in cases if c["project"] == project]
        dataset_text += row(
            NAMES[project],
            LANG[project],
            len(selected),
            f"{statistics.mean(c['buggy']['files'] for c in selected):.1f}",
            f"{statistics.mean(c['buggy']['lines'] for c in selected):.1f}",
        )
        verification_text += row(
            NAMES[project],
            len(selected),
            sum(c["verification_route"] == "mechanical" for c in selected),
            sum(c["verification_route"] == "human" for c in selected),
        )
        counts = [
            sum(
                r["detected"]
                for r in results
                if r["task_type"] == "buggy" and r["model"] == model and r["project"] == project
            )
            for model in ORDER
        ]
        project_text += row(NAMES[project], len(selected), *counts)
    dataset_text += "\\midrule\n" + row(
        "Total", "---", n, f"{stats['mean_files']:.1f}", f"{stats['mean_lines']:.1f}"
    )
    verification_text += "\\midrule\n" + row(
        "Total", n, stats["verification_routes"]["mechanical"], stats["verification_routes"]["human"]
    )
    write("verified_dataset_rows.tex", dataset_text)
    write("baseline_verification_rows.tex", verification_text)
    write("baseline_project_rows.tex", project_text)
    size_text = ""
    for low, high in [(1, 1), (2, 5), (6, 10), (11, 30)]:
        keys = {(c["project"], c["bug_id"]) for c in cases if low <= c["buggy"]["files"] <= high}
        counts = [
            sum(
                r["detected"]
                for r in results
                if r["task_type"] == "buggy" and r["model"] == model and (r["project"], r["bug_id"]) in keys
            )
            for model in ORDER
        ]
        size_text += row(str(low) if low == high else f"{low}--{high}", len(keys), *counts)
    write("baseline_size_rows.tex", size_text)
    final_macros = {
        "finalVerifiedCases": n,
        "finalVerifiedInputs": 2 * n,
        "finalVerifiedProjects": stats["projects"],
        "finalMechanicalVerifiedCases": stats["verification_routes"]["mechanical"],
        "finalHumanVerifiedCases": stats["verification_routes"]["human"],
        "finalMeanFiles": f"{stats['mean_files']:.1f}",
        "finalMeanLines": f"{stats['mean_lines']:.1f}",
    }
    write(
        "final_verification_macros.tex",
        "".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in final_macros.items()),
    )

    atomic_json(output_dir / "baseline_derived.json", stats)
    return stats


def markdown(stats: dict, labels: dict | None = None) -> str:
    lines = [
        "| Model | Tasks | Scanned | Judged | Detected | Recall | Empty |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for model, kinds in stats["models"].items():
        a = kinds["buggy"]
        recall = f"{100 * a['detected'] / a['assigned']:.1f}%" if a["assigned"] else "n/a"
        lines.append(
            f"| {(labels or {}).get(model, model)} | {a['assigned']} | {a['scanned']} | {a['judged']} | {a['detected']} | {recall} | {a['empty']} |"
        )
    return "\n".join(lines) + "\n"


def register_parser(subparsers: Any) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("report", help="Regenerate frozen paper statistics or summarize new runs")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--snapshot", type=Path, help="Historical or current schema-2 frozen results JSON")
    source.add_argument("--archive-workspace", type=Path, help="Re-read the historical workspace outputs")
    source.add_argument(
        "--run-dir", type=Path, action="append", help="New run directory (repeat for disjoint runs)"
    )
    parser.add_argument("--out", type=Path, required=True, help="New report directory")
    parser.add_argument("--roster", type=Path, help="Archive roster TSV override")
    parser.add_argument(
        "--audit-workspace", type=Path, help="Audit frozen source hashes without changing results"
    )
    parser.add_argument(
        "--paper-tables", action="store_true", help="Generate the original five-model LaTeX table rows"
    )
    parser.add_argument("--case-seasons", type=Path, help="JSON mapping project/bug_id to YYYYH1 or YYYYH2")
    parser.add_argument(
        "--model-cutoffs", type=Path, help="JSON mapping model names to ISO knowledge-cutoff dates"
    )
    parser.set_defaults(func=main)
    return parser


def main(args: argparse.Namespace) -> int:
    args.out.mkdir(parents=True, exist_ok=True)
    cutoffs = json.loads(args.model_cutoffs.read_text()) if args.model_cutoffs else {}
    if args.run_dir:
        atomic_json(args.out / "results.json", summarize_runs(args.run_dir, model_cutoffs=cutoffs))
        print(f"Wrote run report to {args.out / 'results.json'}")
        return 0
    snapshot = (
        json.loads(args.snapshot.read_text())
        if args.snapshot
        else freeze_archive(args.archive_workspace, roster_path=args.roster)
    )
    if args.archive_workspace:
        atomic_json(args.out / "baseline_results.json", snapshot)
    current_snapshot = "cases" not in snapshot and snapshot.get("schema_version") == 2
    if current_snapshot and args.paper_tables:
        raise ValueError("--paper-tables is for the historical five-model snapshot; omit it for current results")
    snapshot = normalize_snapshot(snapshot)
    stats = write_paper_tables(snapshot, args.out) if args.paper_tables else derive(snapshot)
    if current_snapshot:
        stats["interpretation"] = (
            "Frozen target-hit verdicts, with missing or incomplete assignments retained in the denominator. "
            "Companion target hits are not calibrated false-positive rates."
        )
    atomic_json(args.out / "baseline_derived.json", stats)
    (args.out / "recall.md").write_text(markdown(stats, snapshot.get("models")), encoding="utf-8")
    if args.audit_workspace:
        atomic_json(args.out / "source_audit.json", audit_sources(args.audit_workspace, snapshot))
    if args.case_seasons:
        seasons = json.loads(args.case_seasons.read_text())
        atomic_json(
            args.out / "seasons.json",
            summarize_seasons(snapshot, case_seasons=seasons, model_cutoffs=cutoffs),
        )
    print(markdown(stats, snapshot.get("models")))
    return 0
