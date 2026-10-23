"""Execute the vendored reference skill inside the sandbox."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from ..runtime import argument_parser, load_input, save_predictions
from .convert import convert_findings

TOOLS = [
    "Read",
    "Glob",
    "Grep",
    "Write",
    "Task",
    "Bash(rg:*)",
    "Bash(grep:*)",
    "Bash(ls:*)",
    "Bash(wc:*)",
    "Bash(head:*)",
    "Bash(file:*)",
]


def main(argv=None) -> int:
    parser = argument_parser(__doc__)
    parser.add_argument("--no-score", action="store_true")
    args = parser.parse_args(argv)
    review, run_id = load_input(args)
    started = time.monotonic()
    output_path = args.workspace / "VULN-FINDINGS.json"
    if output_path.exists():
        raise ValueError("workspace contains stale VULN-FINDINGS.json")
    with tempfile.TemporaryDirectory(prefix="defending-") as directory:
        home = Path(directory)
        skill = home / ".claude" / "skills" / "vuln-scan"
        skill.mkdir(parents=True)
        shutil.copyfile(Path(__file__).with_name("skill") / "SKILL.md", skill / "SKILL.md")
        prompt = f"/vuln-scan {shlex.quote(str(args.workspace))} --extra {shlex.quote(str(args.input.with_name('brief.md')))}"
        for f in review.files:
            prompt += " --focus " + shlex.quote(f.path)
        if args.no_score:
            prompt += " --no-score"
        command = [
            "claude",
            "-p",
            "--verbose",
            "--output-format",
            "stream-json",
            "--permission-mode",
            "bypassPermissions",
            "--model",
            args.model,
            "--tools",
            ",".join(TOOLS),
            "--add-dir",
            str(args.workspace),
            "--strict-mcp-config",
        ]
        if args.max_turns:
            command += ["--max-turns", str(args.max_turns)]
        command.append(prompt)
        env = os.environ.copy()
        env.pop("CLAUDECODE", None)
        trajectory = args.output.parent / "trajectory.jsonl"
        with trajectory.open("w") as stdout, (args.output.parent / "stderr.log").open("w") as stderr:
            result = subprocess.run(command, cwd=home, env=env, stdout=stdout, stderr=stderr, check=False)
        if result.returncode:
            raise RuntimeError(f"reference harness exited with status {result.returncode}; see stderr.log")
        events = [json.loads(line) for line in trajectory.read_text().splitlines() if line.startswith("{")]
        final = next((event for event in reversed(events) if event.get("type") == "result"), None)
        if not final or final.get("is_error") or final.get("subtype") not in {"success", None}:
            raise RuntimeError("reference harness did not complete successfully; see trajectory.jsonl")
        if not output_path.is_file():
            raise RuntimeError("reference harness did not create VULN-FINDINGS.json")
        data = json.loads(output_path.read_text())
        shutil.copyfile(output_path, args.output.parent / "reference_findings.json")
        usage = final.get("usage") or {}
        save_predictions(
            args,
            review,
            run_id,
            convert_findings(data),
            scanner_version="secprbench-defending-0.1.0",
            elapsed_seconds=time.monotonic() - started,
            tokens_in=int(
                usage.get("input_tokens", 0)
                + usage.get("cache_read_input_tokens", 0)
                + usage.get("cache_creation_input_tokens", 0)
            ),
            tokens_out=int(usage.get("output_tokens", 0)),
            trajectory_uri="trajectory.jsonl",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
