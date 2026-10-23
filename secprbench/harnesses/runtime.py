"""Shared in-container runtime; no host paths or evaluation metadata."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

from secprbench.io import write_json
from secprbench.schema import ReviewInput

from .contract import validate_predictions


def argument_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--input", type=Path, default=Path("/task/input.json"))
    parser.add_argument("--output", type=Path, default=Path("/out/findings.json"))
    parser.add_argument("--workspace", type=Path, default=Path("/workspace"))
    parser.add_argument("--model", required=True)
    parser.add_argument("--project", default="")
    parser.add_argument("--max-turns", type=int, default=0)
    return parser


def load_input(args) -> tuple[ReviewInput, str]:
    review = ReviewInput.model_validate_json(args.input.read_text())
    run_id = os.environ.get("SECPRBENCH_RUN_ID", "")
    if not re.fullmatch(r"[0-9a-f]{12}", run_id):
        raise ValueError("SECPRBENCH_RUN_ID must be an opaque 12-character hexadecimal ID")
    if not args.workspace.is_dir():
        raise ValueError("workspace does not exist")
    if args.max_turns < 0:
        raise ValueError("max-turns must be nonnegative")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    return review, run_id


def save_predictions(args, review, run_id: str, predictions: list[dict], **metrics) -> dict:
    result = validate_predictions(
        {"instance_id": run_id, "model": args.model, "predictions": predictions, **metrics},
        review,
        instance_id=run_id,
    )
    write_json(args.output, result)
    return result


def read_json_object(text: str) -> dict:
    """Decode the first actual JSON object, handling strings containing braces."""
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("no JSON object found")


def require_claude_success(paths) -> None:
    """Reject CLI errors that older caw versions did not propagate."""
    completed = False
    for path in paths:
        for line in path.read_text().splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "result":
                if event.get("is_error") or event.get("subtype") not in {"success", None}:
                    raise RuntimeError("Claude CLI returned an incomplete or failed review; see trajectory")
                completed = True
    if not completed:
        raise RuntimeError("Claude CLI emitted no successful completion event")


@contextmanager
def claude_turn_limit(max_turns: int):
    """Enforce the CLI limit even when caw does not forward this option.

    The shim resolves the already pinned executable before changing PATH. It
    affects only the in-container harness process and is removed on exit.
    """
    if not max_turns:
        yield
        return
    executable = shutil.which("claude")
    if executable is None:
        raise FileNotFoundError("claude CLI is not installed")
    previous = os.environ.get("PATH", "")
    with tempfile.TemporaryDirectory(prefix="secprbench-cli-") as directory:
        shim = Path(directory) / "claude"
        import sys

        shim.write_text(
            f"#!{sys.executable} -I\nimport os, sys\n"
            f"os.execv({executable!r}, [{executable!r}, '--max-turns', {str(max_turns)!r}, *sys.argv[1:]])\n"
        )
        shim.chmod(0o700)
        os.environ["PATH"] = directory + os.pathsep + previous
        try:
            yield
        finally:
            os.environ["PATH"] = previous
