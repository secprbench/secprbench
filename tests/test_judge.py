import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from secprbench.judge.criteria_first import build_eval_prompt, extract_json_object, format_findings_text
from secprbench.judge.runner import (
    caw_completion,
    judge_run,
    judge_task,
    normalize_findings,
    normalize_verdict,
)

FIXTURE = Path(__file__).parent / "fixtures/judge_parity.json"


class JudgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE.read_text())

    def test_archived_prompt_is_byte_identical(self):
        f = self.fixture
        self.assertEqual(
            build_eval_prompt(
                f["task"]["bug_id"],
                f["task"],
                f["task"]["ground_truth"],
                format_findings_text(f["findings"]),
                30000,
            ),
            f["prompt"],
        )
        result = extract_json_object(f["response"])
        self.assertIsInstance(result["detected"], bool)

    def test_response_parser_nested_escaped_and_fences(self):
        obj = {"detected": False, "criteria": ['quote: " } \\'], "nested": {"a": 1}}
        payload = json.dumps(obj)
        for text in (payload, "prefix\n" + payload + "\nsuffix", "```json\n" + payload + "\n```"):
            self.assertEqual(extract_json_object(text), obj)
        for text in ("", "API Error: 529 Overloaded.", "[]"):
            with self.assertRaises(ValueError):
                extract_json_object(text)

    def test_malformed_verdict_never_becomes_positive(self):
        for result in (
            {"detected": "false"},
            {"detected": True, "bug_id": "other"},
            {"detected": True, "current_code_support": "fixed"},
            {"detected": False, "match_score": "NaN"},
        ):
            with self.assertRaises(ValueError):
                normalize_verdict("target", result, 1)

    def test_public_prediction_locations(self):
        findings = normalize_findings(
            {"predictions": [{"title": "issue", "file": "src/a.c", "start_line": 12}]}
        )
        self.assertEqual(findings[0]["location"], {"file": "src/a.c", "start_line": 12})

    def test_retries_fingerprint_resume_and_empty(self):
        f = self.fixture
        calls = []

        def complete(prompt, **kwargs):
            calls.append(prompt)
            return "API Error" if len(calls) == 1 else '{"detected": false}'

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            result = judge_task(f["task"], f["task"]["ground_truth"], f["findings"], out, complete=complete)
            self.assertTrue(result["completed"])
            self.assertEqual(len(calls), 2)
            self.assertEqual(
                judge_task(f["task"], f["task"]["ground_truth"], f["findings"], out, complete=complete),
                result,
            )
            self.assertEqual(len(calls), 2)
            judge_task(
                f["task"], f["task"]["ground_truth"], f["findings"], out, model="different", complete=complete
            )
            self.assertEqual(len(calls), 3)
            result = judge_task(f["task"], f["task"]["ground_truth"], [], out, complete=complete)
            self.assertEqual(result["verification_method"], "empty-output")
            self.assertEqual(len(calls), 3)

    def test_tool_judge_process_really_uses_snapshot_cwd(self):
        seen = []

        def run(*args, **kwargs):
            seen.append(kwargs)
            self.assertTrue(Path(kwargs["cwd"]).is_dir())
            return SimpleNamespace(returncode=0, stdout='{"response":"ok"}', stderr="")

        with patch("secprbench.judge.runner.subprocess.run", run):
            self.assertEqual(caw_completion("prompt", model="test"), "ok")
            self.assertFalse(json.loads(seen[-1]["input"])["paper_tools"])
            with tempfile.TemporaryDirectory() as tmp:
                caw_completion("prompt", model="test", paper_tools=True, workspace=Path(tmp))
                self.assertEqual(seen[-1]["cwd"], str(Path(tmp).resolve()))
            with self.assertRaises(ValueError):
                caw_completion("prompt", model="test", paper_tools=True)

    def test_no_tool_worker_disables_builtins_mcp_and_settings(self):
        from secprbench.judge.worker import complete

        seen = []

        def run(command, **kwargs):
            seen.append(command)
            return SimpleNamespace(returncode=0, stdout='{"result":"verdict","is_error":false}', stderr="")

        with patch("secprbench.judge.worker.subprocess.run", run):
            self.assertEqual(
                complete({"model": "test", "prompt": "prompt", "paper_tools": False, "no_web": True}),
                "verdict",
            )
        command = seen[0]
        self.assertEqual(command[command.index("--tools") + 1], "")
        self.assertIn("--strict-mcp-config", command)
        self.assertEqual(json.loads(command[command.index("--mcp-config") + 1]), {"mcpServers": {}})
        self.assertIn("--disable-slash-commands", command)

    def test_no_tool_worker_preserves_only_structured_oauth_failure(self):
        from secprbench.judge.worker import complete

        request = {"model": "test", "prompt": "prompt", "paper_tools": False, "no_web": True}
        expired = "Failed to authenticate: OAuth session expired and could not be refreshed"
        with patch("secprbench.judge.worker.subprocess.run") as run:
            run.return_value = SimpleNamespace(
                returncode=1,
                stdout=json.dumps({"is_error": True, "result": expired}),
                stderr="",
            )
            with self.assertRaisesRegex(RuntimeError, expired):
                complete(request)
            run.return_value = SimpleNamespace(
                returncode=1,
                stdout=json.dumps({"is_error": True, "result": "unrelated private output"}),
                stderr="",
            )
            with self.assertRaises(RuntimeError) as failure:
                complete(request)
            self.assertNotIn("private output", str(failure.exception))

    def test_auth_is_copied_to_private_ephemeral_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "auth.json"
            source.write_text('{"test": "credential"}')
            seen = []

            def run(*args, **kwargs):
                folder = Path(kwargs["env"]["CLAUDE_CONFIG_DIR"])
                seen.append(folder)
                self.assertEqual((folder / ".credentials.json").read_text(), source.read_text())
                self.assertEqual((folder / ".credentials.json").stat().st_mode & 0o777, 0o600)
                return SimpleNamespace(returncode=0, stdout='{"response":"ok"}', stderr="")

            with (
                patch.dict(os.environ, {"SECPRBENCH_JUDGE_AUTH_FILE": str(source)}),
                patch("secprbench.judge.runner.subprocess.run", run),
            ):
                caw_completion("prompt", model="test")
            self.assertFalse(seen[0].exists())
            self.assertEqual(source.read_text(), '{"test": "credential"}')

    def test_manifest_refuses_modified_task_or_findings(self):
        import hashlib

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = root / "pr_review_target.json"
            task.write_text(json.dumps(self.fixture["task"]))
            out = root / "out"
            out.mkdir()
            findings = out / "findings.json"
            findings.write_text('{"predictions": []}')
            record = {
                "task_id": "target",
                "task_path": str(task),
                "output_dir": str(out),
                "status": "succeeded",
                "task_sha256": hashlib.sha256(task.read_bytes()).hexdigest(),
                "findings_sha256": hashlib.sha256(findings.read_bytes()).hexdigest(),
            }
            for field in ("task_sha256", "findings_sha256"):
                bad = {**record, field: "0" * 64}
                (root / "manifest.json").write_text(json.dumps({"tasks": [bad]}))
                summary = judge_run(root)
                self.assertFalse(summary["evals"])
                self.assertEqual(len(summary["errors"]), 1)

    def test_manifest_judging_and_benign_reference(self):
        task = self.fixture["task"]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks = root / "tasks"
            tasks.mkdir()
            (tasks / "pr_review_bug.json").write_text(json.dumps(task))
            benign = {**task, "task_type": "benign", "ground_truth": {"expected_finding": False}}
            task_path = tasks / "pr_review_bug_benign.json"
            task_path.write_text(json.dumps(benign))
            out = root / "opaque/out"
            out.mkdir(parents=True)
            (out / "findings.json").write_text(json.dumps({"predictions": []}))
            (root / "manifest.json").write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "private",
                                "task_path": str(task_path),
                                "output_dir": str(out),
                                "status": "succeeded",
                            }
                        ]
                    }
                )
            )
            summary = judge_run(root)
            self.assertFalse(summary["errors"])
            self.assertFalse(summary["evals"]["private"]["detected"])
            self.assertTrue((out / "verdict.json").exists())
            prompt = (out / "judge_logs/bench_eval_verifier_prompt.txt").read_text()
            self.assertIn(task["ground_truth"]["root_cause"], prompt)


if __name__ == "__main__":
    unittest.main()
