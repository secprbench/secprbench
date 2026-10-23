"""Private judge process; the parent selects an empty directory or pinned snapshot."""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
from typing import Any

from .runner import SYSTEM_PROMPT

CLAUDE_OAUTH_EXPIRED = "Failed to authenticate: OAuth session expired and could not be refreshed"


def complete(request: dict[str, Any]) -> str:
    binary = os.environ.get("SECPRBENCH_CLAUDE", "claude")
    expected_version = request.get("claude_version")
    if expected_version:
        version = subprocess.run([binary, "--version"], capture_output=True, text=True,
                                 check=True, timeout=30).stdout.strip()
        if version.split(maxsplit=1)[0] != expected_version:
            raise ValueError(f"Expected Claude CLI {expected_version}, got {version}")
    effort = request.get("reasoning_effort")
    if effort not in (None, "low", "medium", "high", "max"):
        raise ValueError("Invalid judge reasoning effort")
    if request["paper_tools"]:
        if effort:
            raise ValueError("Historical caw tool-enabled judging requires reasoning_effort: null")
        import caw

        tools = caw.ToolGroup.NO_INTERACTION
        if request["no_web"]:
            tools = tools - caw.ToolGroup.WEB
        with contextlib.redirect_stdout(sys.stderr):
            agent = caw.Agent(system_prompt=SYSTEM_PROMPT, model=request["model"], tools=tools)
            return str(agent.completion(request["prompt"]).result or "")
    # caw's Claude provider rejects an empty ToolGroup. CLI --tools "" removes
    # the tools from the model's schema; disabling built-in names is insufficient
    # because user/global MCP configuration could introduce additional tools.
    command = [
        binary,
        "--print",
        "--output-format",
        "json",
        "--model",
        request["model"],
        "--system-prompt",
        SYSTEM_PROMPT,
        "--tools",
        "",
        "--strict-mcp-config",
        "--mcp-config",
        '{"mcpServers":{}}',
        "--disable-slash-commands",
        "--setting-sources",
        "",
        "--no-session-persistence",
    ]
    if effort:
        command += ["--effort", effort]
    proc = subprocess.run(
        command, input=request["prompt"], capture_output=True, text=True, check=False, timeout=1100
    )
    if proc.returncode:
        detail = proc.stderr[-2000:]
        try:
            payload = json.loads(proc.stdout)
        except (TypeError, ValueError):
            payload = None
        if (
            isinstance(payload, dict)
            and payload.get("is_error") is True
            and isinstance(payload.get("result"), str)
            and CLAUDE_OAUTH_EXPIRED in payload["result"]
        ):
            # Keep the exact provider signal without logging arbitrary CLI output.
            detail = CLAUDE_OAUTH_EXPIRED
        raise RuntimeError(f"Judge CLI failed ({proc.returncode}): {detail}")
    payload = json.loads(proc.stdout)
    if payload.get("is_error"):
        raise RuntimeError(str(payload.get("result", "Judge CLI reported an error")))
    response = payload.get("result")
    if not isinstance(response, str):
        raise TypeError("Judge CLI returned no text result")
    return response


def main() -> None:
    request = json.load(sys.stdin)
    print(json.dumps({"response": complete(request)}))


if __name__ == "__main__":
    main()
