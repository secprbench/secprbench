"""Read-only checks of archived raw outputs, including post-freeze changes."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from secprbench.report.aggregate import derive
from secprbench.report.archive import audit_sources, freeze_archive
from secprbench.report.tables import write_paper_tables

ROOT = Path(os.environ.get("SECPRBENCH_ARCHIVE_ROOT", Path(__file__).parent / "fixtures/unavailable-archive"))
BASE = Path(os.environ.get("SECPRBENCH_LEGACY_DATA_ROOT", str(ROOT / "secprbench/data"))) / "paper"


@unittest.skipUnless((ROOT / "tmp/anth_opus_verified_tasks.tsv").is_file() and (BASE / "baseline_results.json").is_file(), "Historical archives unavailable")
class RawArchiveTests(unittest.TestCase):
    def test_current_raw_freeze_and_original_hash_audit(self):
        frozen = json.loads((BASE / "baseline_results.json").read_text())
        current = freeze_archive(ROOT)
        self.assertEqual(len(current["cases"]), 160)
        self.assertEqual(len(current["results"]), 1600)
        self.assertEqual(current["unreadable_json"], [])
        stats = derive(current)
        for model in ("opus", "grok", "minimax", "gpt"):
            self.assertEqual(
                stats["models"][model]["buggy"]["detected"],
                derive(frozen)["models"][model]["buggy"]["detected"],
            )
        audit = audit_sources(ROOT, frozen)
        self.assertEqual(audit["checked"], 7853)
        self.assertEqual(audit["missing"], [])
        self.assertEqual(audit["matched"] + len(audit["changed"]), audit["checked"])
        # Historical artifacts have legitimately advanced; do not replace frozen scores.
        self.assertGreaterEqual(stats["models"]["gpt"]["benign"]["scanned"], 40)

    def test_all_original_paper_table_bodies_match(self):
        snapshot = json.loads((BASE / "baseline_results.json").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            write_paper_tables(snapshot, out)
            for path in out.glob("*.tex"):
                historical = (ROOT / "secprbench-paper/tables" / path.name).read_text()
                self.assertEqual(
                    path.read_text(), "".join(historical.splitlines(keepends=True)[1:]), path.name
                )


if __name__ == "__main__":
    unittest.main()
