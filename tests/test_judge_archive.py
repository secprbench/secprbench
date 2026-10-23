"""Optional broad regression against the read-only local historical archives."""

import os
import unittest
from pathlib import Path

from secprbench.judge.criteria_first import build_eval_prompt, extract_json_object, format_findings_text
from secprbench.judge.runner import load_findings, load_task_maps

ROOT = Path(os.environ.get("SECPRBENCH_ARCHIVE_ROOT", Path(__file__).parent / "fixtures/unavailable-archive"))
PROJECTS = ("curl", "ffmpeg", "firefox", "freetype", "openssl", "redis", "sqlite", "v8", "wasmtime")


@unittest.skipUnless((ROOT / "bench/pr_bench_curl").is_dir(), "Historical archives unavailable")
class ArchivedJudgeTests(unittest.TestCase):
    def test_all_archived_baseline_prompts_and_responses(self):
        matched = parsed = rejected = 0
        for project in PROJECTS:
            tasks, refs = load_task_maps(ROOT / f"cgsa_datasets/{project}/pr_tasks", "buggy")
            for path in (ROOT / f"bench/pr_bench_{project}").glob(
                "bench_base_recall_*/bug_*/logs/bench_eval_verifier_prompt.txt"
            ):
                bug = path.parents[1].name[4:]
                if bug not in tasks:
                    continue
                findings = load_findings(path.parents[1], archival=True)
                with self.subTest(path=str(path)):
                    self.assertEqual(
                        build_eval_prompt(bug, tasks[bug], refs[bug], format_findings_text(findings), 30000),
                        path.read_text(),
                    )
                matched += 1
                for response in path.parent.glob("bench_eval_verifier_attempt_*.txt"):
                    try:
                        extract_json_object(response.read_text())
                        parsed += 1
                    except ValueError:
                        self.assertTrue(response.with_suffix(".error.json").exists(), str(response))
                        rejected += 1
        self.assertGreaterEqual(matched, 1000)
        self.assertGreaterEqual(parsed, matched)
        self.assertGreaterEqual(rejected, 3)


if __name__ == "__main__":
    unittest.main()
