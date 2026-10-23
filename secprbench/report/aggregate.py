"""Paper-compatible accounting with explicit partial-run denominators."""

from __future__ import annotations

import statistics
from collections import Counter

ORDER = ("opus", "grok", "glm", "minimax", "gpt")
LABELS = {
    "opus": "Claude Opus 5",
    "grok": "Grok 4.6",
    "glm": "GLM 5.3",
    "minimax": "MiniMax M3",
    "gpt": "GPT-5.6 sol (xhigh)",
}
NAMES = {
    "curl": "curl",
    "ffmpeg": "FFmpeg",
    "firefox": "Firefox",
    "freetype": "FreeType",
    "openssl": "OpenSSL",
    "redis": "Redis",
    "sqlite": "SQLite",
    "v8": "V8",
    "wasmtime": "Wasmtime",
}
LANG = {p: ("Rust" if p == "wasmtime" else "C++" if p in {"firefox", "v8"} else "C") for p in NAMES}


def model_order(snapshot):
    return tuple(m for m in ORDER if m in snapshot["models"]) + tuple(
        m for m in snapshot["models"] if m not in ORDER
    )


def aggregate(rows):
    scanned = [r for r in rows if r["scanned"]]
    n = len(scanned)
    durations = [r["usage"]["duration_ms"] for r in scanned if r["usage"].get("duration_ms") is not None]
    sums = {
        k: sum(r["usage"].get(k, 0) or 0 for r in scanned)
        for k in (
            "output_tokens",
            "input_tokens",
            "cache_read_tokens",
            "cache_write_tokens",
            "duration_ms",
            "cost_usd",
        )
    }
    return {
        "assigned": len(rows),
        "scanned": n,
        "judged": sum(r["judged"] for r in rows),
        "detected": sum(r["detected"] for r in rows),
        "unjudged_findings": sum(r["status"] == "awaiting_judgment" for r in rows),
        "unscanned": len(rows) - n,
        "empty": sum(r["reports"] == 0 and r["status"] != "invalid_output" for r in scanned),
        "reports": sum(r["reports"] for r in scanned),
        "any_report": sum(r["reports"] > 0 for r in scanned),
        "reports_per_scan": sum(r["reports"] for r in scanned) / n if n else None,
        "mean_output_tokens": sums["output_tokens"] / n if n else None,
        "median_minutes": statistics.median(durations) / 60000 if durations else None,
        "usage": sums,
        "judge_report_count_mismatches": [
            f"{r['project']}/{r['bug_id']}"
            for r in scanned
            if r["judged"] and r["judge"].get("num_findings") != r["reports"]
        ],
    }


def derive(snapshot):
    cases, results = snapshot["cases"], snapshot["results"]
    keys = {(c["project"], c["bug_id"]) for c in cases}
    if not cases or len(keys) != len(cases):
        raise ValueError("Cases must be nonempty and unique")
    order = model_order(snapshot)
    if not all(c[k]["files"] > 0 for c in cases for k in ("buggy", "benign")):
        raise ValueError("Every paired task must have changed files")
    stats = {
        "captured_at": snapshot["captured_at"],
        "buggy": len(cases),
        "benign": len(cases),
        "instances": 2 * len(cases),
        "projects": len({c["project"] for c in cases}),
        "distinct_introductions": len({(c["project"], c["buggy"]["intro_commit_sha"]) for c in cases}),
        "verification_routes": dict(Counter(c["verification_route"] for c in cases)),
        "mean_files": statistics.mean(c["buggy"]["files"] for c in cases),
        "mean_lines": statistics.mean(c["buggy"]["lines"] for c in cases),
        "median_files": statistics.median(c["buggy"]["files"] for c in cases),
        "median_lines": statistics.median(c["buggy"]["lines"] for c in cases),
        "models": {},
    }
    for model in order:
        stats["models"][model] = {}
        for kind in ("buggy", "benign"):
            rows = [r for r in results if r["model"] == model and r["task_type"] == kind]
            if len(rows) != len(keys) or {(r["project"], r["bug_id"]) for r in rows} != keys:
                raise ValueError(f"Results do not match roster: {model}/{kind}")
            if not all(
                not r["detected"] or (r["scanned"] and r["judged"] and r["judge"]["detected"]) for r in rows
            ):
                raise ValueError(f"Inconsistent detected result: {model}/{kind}")
            stats["models"][model][kind] = aggregate(rows)
    return stats


def derive_comparison(snapshot, stats):
    order = model_order(snapshot)
    keys = {(c["project"], c["bug_id"]) for c in snapshot["cases"]}
    rows = {
        model: [r for r in snapshot["results"] if r["model"] == model and r["task_type"] == "buggy"]
        for model in order
    }
    for model in order:
        a = stats["models"][model]["buggy"]
        if a["scanned"] != len(keys) or a["unjudged_findings"]:
            raise ValueError(f"Comparison requires complete buggy scans: {model}")
    hits = {model: {(r["project"], r["bug_id"]) for r in rows[model] if r["detected"]} for model in order}
    detected_by = Counter(sum(key in hits[m] for m in order) for key in keys)
    union = set.union(*hits.values())
    best = max(order, key=lambda m: len(hits[m]))
    complete_benign = [
        m
        for m in order
        if stats["models"][m]["benign"]["scanned"] == len(keys)
        and not stats["models"][m]["benign"]["unjudged_findings"]
    ]
    opus = stats["models"].get("opus", {}).get("buggy", {})
    glm = stats["models"].get("glm", {}).get("buggy", {})
    return {
        "source": "baseline_results.json",
        "task_count": len(keys),
        "models_detecting_target": {str(i): detected_by[i] for i in range(len(order) + 1)},
        "any_model_detected": len(union),
        "shared_miss_cases": ["/".join(key) for key in sorted(keys - union)],
        "highest_recall_model": best,
        "additional_cases_beyond_highest_recall_model": ["/".join(key) for key in sorted(union - hits[best])],
        "misses_by_model": {
            m: {
                "missed": len(keys - hits[m]),
                "nonempty": sum(not r["detected"] and r["reports"] > 0 for r in rows[m]),
                "empty": sum(r["reports"] == 0 for r in rows[m]),
            }
            for m in order
        },
        "benign_to_buggy_report_ratio": {
            m: stats["models"][m]["benign"]["reports"] / stats["models"][m]["buggy"]["reports"]
            if stats["models"][m]["buggy"]["reports"]
            else None
            for m in complete_benign
        },
        "glm_to_opus_usage_ratio": {
            "mean_output_tokens": glm["mean_output_tokens"] / opus["mean_output_tokens"]
            if glm.get("mean_output_tokens") is not None and opus.get("mean_output_tokens")
            else None,
            "median_duration": glm["median_minutes"] / opus["median_minutes"]
            if glm.get("median_minutes") is not None and opus.get("median_minutes")
            else None,
        },
    }
