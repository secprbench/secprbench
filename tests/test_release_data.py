"""Offline release-contract tests; no historical repositories or model credentials."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from check_release import validate  # noqa: E402


class ReleaseDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Real copies ensure the test never mutates the release under review.
        cls.tmp = tempfile.TemporaryDirectory(prefix='secprbench-relocated-')
        cls.root = Path(cls.tmp.name) / 'another checkout'
        cls.root.mkdir()
        for name in ('data', 'instances', 'artifacts', 'provenance'):
            shutil.copytree(ROOT / name, cls.root / name)
        (cls.root / 'tools').mkdir()
        for name in ('check_release.py', 'export_release.py'):
            shutil.copyfile(ROOT / 'tools' / name, cls.root / 'tools' / name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_release_validates_after_relocation_without_original_workspace(self):
        result = subprocess.run(
            [sys.executable, str(self.root / 'tools/check_release.py'), '--root', str(self.root)],
            cwd=self.tmp.name, capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report['ok'])
        self.assertEqual((report['cases'], report['tasks']), (265, 530))
        self.assertEqual(report['pre2021_cases_retained'], 36)
        self.assertEqual(report['historical_result_records'], 4240)
        self.assertTrue(any('CVE-2026-9079' in w for w in report['warnings']))

    def test_one_byte_task_corruption_is_not_a_known_issue_warning(self):
        roster = json.loads((self.root / 'data/roster.json').read_text())
        path = self.root / 'data' / roster['entries'][0]['buggy']['path']
        before = path.read_bytes()
        try:
            path.write_bytes(before + b' ')
            report = validate(self.root)
            self.assertFalse(report['ok'])
            self.assertTrue(any('hash mismatch' in e.lower() or 'sha-256 mismatch' in e.lower() for e in report['errors']))
        finally:
            path.write_bytes(before)

    def test_unlisted_task_payload_rejected(self):
        path = self.root / 'data/2025H1/data/tasks/curl/unlisted.json'
        try:
            path.write_text('{}\n')
            report = validate(self.root)
            self.assertFalse(report['ok'])
            self.assertTrue(any('unlisted' in e for e in report['errors']))
        finally:
            path.unlink(missing_ok=True)

    def test_absolute_roster_path_rejected(self):
        path = self.root / 'data/roster.json'
        before = path.read_bytes()
        roster = json.loads(before)
        roster['entries'][0]['buggy']['path'] = '/outside/checkout/task.json'
        try:
            path.write_text(json.dumps(roster))
            self.assertFalse(validate(self.root)['ok'])
        finally:
            path.write_bytes(before)


if __name__ == '__main__':
    unittest.main()
