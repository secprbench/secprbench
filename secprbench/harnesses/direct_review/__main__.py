"""Execute the paper scanner inside a review container."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from ..runtime import argument_parser, claude_turn_limit, load_input, require_claude_success, save_predictions
from .prompts import build_system_prompt, build_user_prompt


def main(argv=None) -> int:
    parser = argument_parser(__doc__)
    parser.add_argument(
        "--project-context", type=Path, help="Optional public context; omitted for exact paper prompt parity"
    )
    args = parser.parse_args(argv)
    review, run_id = load_input(args)
    from caw import Agent, ToolGroup

    from .reporter import ReviewReporter

    reporter = ReviewReporter(args.output.parent)
    context = args.project_context.read_text() if args.project_context else ""
    system = build_system_prompt(str(args.workspace), context)
    user = build_user_prompt(review)
    (args.output.parent / "system_prompt.md").write_text(system)
    (args.output.parent / "user_prompt.md").write_text(user)
    trajectory = args.output.parent / "trajectory.json"
    agent = Agent(
        name="PR Security Review Agent",
        model=args.model,
        system_prompt=system,
        tools=ToolGroup.NO_INTERACTION - ToolGroup.WEB,
        tool_servers=[reporter],
        data_dir=str(args.output.parent),
    )
    original_cwd = Path.cwd()
    start = time.monotonic()
    try:
        os.chdir(args.workspace)
        with (
            claude_turn_limit(args.max_turns),
            agent.start_session(traj_path=trajectory, metadata={"instance_id": run_id}) as session,
        ):
            session.send(user)
    finally:
        os.chdir(original_cwd)
    data = json.loads(trajectory.read_text())
    require_claude_success(args.output.parent.glob("sessions/*/turns/*_raw_output.jsonl"))
    if data.get("usage_limited"):
        raise RuntimeError("model usage limit reached before review completed")
    usage = data.get("total_usage") or data.get("usage") or {}
    save_predictions(
        args,
        review,
        run_id,
        reporter.findings,
        scanner_version="secprbench-direct-review-0.1.0",
        elapsed_seconds=time.monotonic() - start,
        tokens_in=int(
            usage.get("input_tokens", 0)
            + usage.get("cache_read_tokens", 0)
            + usage.get("cache_write_tokens", 0)
        ),
        tokens_out=int(usage.get("output_tokens", 0)),
        trajectory_uri="trajectory.json",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
