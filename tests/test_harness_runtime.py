"""Offline entrypoint smoke tests exercise real child processes and files."""

import json
import os
import sys

import pytest

from secprbench.harnesses.codex.__main__ import main as codex_main
from secprbench.harnesses.defending.__main__ import main as defending_main
from secprbench.harnesses.runtime import claude_turn_limit

RUN = "012345abcdef"


@pytest.fixture
def case(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "a.c").write_text("void f(void) {}\n")
    inputs = tmp_path / "task"
    inputs.mkdir()
    (inputs / "input.json").write_text(
        json.dumps({"files": [{"path": "a.c", "status": "modified", "diff": "+void f(void) {}"}]})
    )
    (inputs / "brief.md").write_text("Review this pull request")
    output = tmp_path / "out" / "findings.json"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("SECPRBENCH_RUN_ID", RUN)
    args = [
        "--input",
        str(inputs / "input.json"),
        "--output",
        str(output),
        "--workspace",
        str(workspace),
        "--model",
        "test",
    ]
    return bin_dir, args, output


def install_executable(directory, name, body):
    path = directory / name
    path.write_text(f"#!{sys.executable}\n" + body)
    path.chmod(0o700)
    return path


def test_codex_container_entrypoint(case):
    bin_dir, args, output = case
    install_executable(
        bin_dir,
        "codex",
        """import json,sys,os
from pathlib import Path
assert '--skip-git-repo-check' in sys.argv
assert '--ignore-user-config' in sys.argv
features = {sys.argv[i+1] for i,x in enumerate(sys.argv) if x == '--disable'}
assert {'plugins','remote_plugin','apps','skill_search','skill_mcp_dependency_install','workspace_dependencies'} <= features
config = {sys.argv[i+1] for i,x in enumerate(sys.argv) if x == '-c'}
assert {'analytics.enabled=false','otel.metrics_exporter="none"','otel.trace_exporter="none"','otel.exporter="none"','web_search="disabled"'} <= config
prompt = sys.stdin.read()
assert 'report_pr_review' not in prompt
result = {'instance_id': os.environ['SECPRBENCH_RUN_ID'], 'predictions': [{'file':'a.c','title':'example'}]}
Path(sys.argv[sys.argv.index('--output-last-message')+1]).write_text(json.dumps(result))
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':5,'output_tokens':3}}))
""",
    )
    assert codex_main(args) == 0
    data = json.loads(output.read_text())
    assert data["instance_id"] == RUN and data["tokens_in"] == 5
    assert data["predictions"][0]["file"] == "a.c"


def test_codex_failed_process_does_not_publish_success(case):
    bin_dir, args, output = case
    install_executable(bin_dir, "codex", "import sys\nsys.exit(4)\n")
    with pytest.raises(RuntimeError, match="status 4"):
        codex_main(args)
    assert not output.exists()


def test_reference_container_entrypoint(case):
    bin_dir, args, output = case
    install_executable(
        bin_dir,
        "claude",
        """import json,sys,shlex
from pathlib import Path
assert Path('.claude/skills/vuln-scan/SKILL.md').is_file()
parts = shlex.split(sys.argv[-1])
assert parts[0] == '/vuln-scan' and '--extra' in parts and '--focus' in parts
Path(parts[1], 'VULN-FINDINGS.json').write_text(json.dumps({'findings':[{'file':'a.c','title':'candidate','category':'use-after-free','line':1}]}))
print(json.dumps({'type':'result','subtype':'success','usage':{'input_tokens':8,'output_tokens':2}}))
""",
    )
    assert defending_main(args) == 0
    data = json.loads(output.read_text())
    assert data["predictions"][0]["bug_type"] == "UseAfterFree"
    assert data["tokens_out"] == 2


def test_turn_limit_wraps_pinned_executable(case):
    import subprocess

    bin_dir, _, _ = case
    install_executable(bin_dir, "claude", "import sys,json\nprint(json.dumps(sys.argv[1:]))\n")
    before = os.environ["PATH"]
    with claude_turn_limit(3):
        result = subprocess.run(["claude", "-p", "hello"], text=True, capture_output=True, check=True)
        assert json.loads(result.stdout) == ["--max-turns", "3", "-p", "hello"]
    assert os.environ["PATH"] == before


def test_direct_entrypoint_real_caw_and_mcp(case):
    import importlib.util

    if importlib.util.find_spec("caw") is None:
        pytest.skip("optional coding-agent-wrapper dependency not installed")
    # An installed but incompatible caw must fail this test, not be skipped.
    import subprocess

    from pathlib import Path

    bin_dir, args, output = case
    install_executable(
        bin_dir,
        "claude",
        """import asyncio,json,sys
from pathlib import Path
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
prompt = sys.stdin.read()
assert 'Please review the following pull request' in prompt
assert '--max-turns' in sys.argv and sys.argv[sys.argv.index('--max-turns')+1] == '8'
config = json.loads(Path(sys.argv[sys.argv.index('--mcp-config')+1]).read_text())
url = next(iter(config['mcpServers'].values()))['url']
async def report():
    async with streamablehttp_client(url) as (read,write,_):
        async with ClientSession(read,write) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert {t.name for t in tools.tools} >= {'report_pr_review','mark_code_reviewed','batch_mark_code_reviewed'}
            result = await session.call_tool('report_pr_review', {'json_finding':json.dumps({'title':'MCP example','message':'Round-trip finding','location':{'file':'a.c','start_line':1}})})
            assert not result.isError, str(result)
asyncio.run(report())
print(json.dumps({'type':'assistant','message':{'content':[{'type':'text','text':'Review complete'}]}}))
print(json.dumps({'type':'result','subtype':'success','is_error':False,'duration_ms':1,'total_cost_usd':0,'usage':{'input_tokens':8,'output_tokens':2}}))
""",
    )
    workspace = Path(args[args.index("--workspace") + 1])
    (workspace / "secprbench.py").write_text("raise RuntimeError('untrusted package shadow loaded')\n")
    marker = workspace / "startup-code-executed"
    (workspace / "sitecustomize.py").write_text(f"from pathlib import Path\nPath({str(marker)!r}).touch()\n")
    result = subprocess.run(
        [sys.executable, "-I", "-m", "secprbench.harnesses.direct_review", *args, "--max-turns", "8"],
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert not marker.exists(), "untrusted snapshot code ran during Python startup"
    data = json.loads(output.read_text())
    assert data["predictions"][0]["title"] == "MCP example"
    assert data["tokens_out"] == 2
    trajectory = json.loads(output.with_name("trajectory.json").read_text())
    assert trajectory["metadata"] == {"instance_id": RUN}
