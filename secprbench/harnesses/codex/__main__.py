"""Run Codex with public diff context and a strict JSON result schema."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

from ..direct_review.prompts import build_user_prompt
from ..runtime import argument_parser, load_input, read_json_object, save_predictions


# Pin startup behavior as well as the model. Ignoring user config alone still
# enables remote plugin downloads and the default Statsig metrics exporter in
# Codex 0.149.1. These controls keep the reference harness limited to code review
# without broadening the sandbox's model/authentication egress allowlist.
DISABLED_STARTUP_FEATURES = (
    "plugins",
    "remote_plugin",
    "apps",
    "skill_search",
    "skill_mcp_dependency_install",
    "workspace_dependencies",
)
CODEX_CONFIG_OVERRIDES = (
    "analytics.enabled=false",
    'otel.metrics_exporter="none"',
    'otel.trace_exporter="none"',
    'otel.exporter="none"',
    'web_search="disabled"',
)


def startup_options() -> list[str]:
    """Return explicit controls verified against the pinned CLI."""
    options = [part for feature in DISABLED_STARTUP_FEATURES for part in ("--disable", feature)]
    options += [part for override in CODEX_CONFIG_OVERRIDES for part in ("-c", override)]
    return options


def main(argv=None) -> int:
    parser = argument_parser(__doc__)
    parser.add_argument("--reasoning-effort", default="medium")
    args = parser.parse_args(argv)
    review, run_id = load_input(args)
    if args.max_turns:
        raise ValueError("Codex CLI does not expose a supported turn limit; use the host timeout budget")
    prompt = (
        "Review the source in /workspace for security issues introduced or made reachable by the diff. "
        "Do not use the network or repository history. Report findings only in changed files. "
        "Return a JSON object with instance_id, model, and predictions, using the attached schema. "
        "Each prediction has title, message, file, bug_type, severity, confidence, and line numbers. "
        "An empty predictions array is valid when no security issues are found.\n"
        f"instance_id: {run_id}\nmodel: {args.model}\n\n"
    )
    # The direct-review user text refers to MCP tools unavailable in Codex;
    # pass only the review content before the tool workflow instructions.
    prompt += build_user_prompt(review, coverage_tracking=False).split("\n**Instructions:**\n", 1)[0]
    final = args.output.parent / "last_message.json"
    command = [
        "codex",
        "exec",
        "--ignore-user-config",
        "--ignore-rules",
        *startup_options(),
        "--skip-git-repo-check",
        "--ephemeral",
        "--json",
        "--dangerously-bypass-approvals-and-sandbox",
        "--model",
        args.model,
        "-c",
        f'model_reasoning_effort="{args.reasoning_effort}"',
        "--output-schema",
        str(Path(__file__).with_name("output.schema.json")),
        "--output-last-message",
        str(final),
        "-",
    ]
    started = time.monotonic()
    trajectory = args.output.parent / "trajectory.jsonl"
    env = os.environ.copy()
    with trajectory.open("w") as stdout, (args.output.parent / "stderr.log").open("w") as stderr:
        result = subprocess.run(
            command,
            input=prompt,
            text=True,
            cwd=args.workspace,
            env=env,
            stdout=stdout,
            stderr=stderr,
            check=False,
        )
    if result.returncode:
        raise RuntimeError(f"Codex exited with status {result.returncode}; see stderr.log")
    output = read_json_object(final.read_text())
    if output.get("instance_id") != run_id:
        raise ValueError("Codex returned an incorrect instance_id")
    if not isinstance(output.get("predictions"), list):
        raise ValueError("Codex did not return a predictions array")  # noqa: TRY004 - invalid public contract
    tokens_in = tokens_out = 0
    completed = False
    for line in trajectory.read_text().splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") in {"error", "turn.failed"}:
            raise RuntimeError("Codex reported a failed turn; see trajectory.jsonl")
        if event.get("type") == "turn.completed":
            completed = True
            usage = event.get("usage") or {}
            tokens_in += int(usage.get("input_tokens", 0))
            tokens_out += int(usage.get("output_tokens", 0))
    if not completed:
        raise RuntimeError("Codex emitted no completed turn")
    save_predictions(
        args,
        review,
        run_id,
        output["predictions"],
        scanner_version="secprbench-codex-0.1.0",
        elapsed_seconds=time.monotonic() - started,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        trajectory_uri="trajectory.jsonl",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
