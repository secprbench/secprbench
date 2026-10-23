"""Classify target and peer progress for curl/GH-16955, not elapsed time alone."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BODY_SHA = "341aacac661ccb210720bedaa9ead5d668fe5ea41a73532fc147c71e34040df1"
FULL = 16_777_216
STALLED = 10_485_760


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--client-log", type=Path, required=True)
    parser.add_argument("--client-rc", type=int, required=True)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_bytes())
    report = json.loads(args.report.read_bytes())
    if (spec != {"fast_bytes": FULL, "slow_bytes": FULL, "body_sha256": BODY_SHA}
            or report["fixture"]["fast_length"] != FULL
            or report["fixture"]["slow_length"] != FULL
            or report["fixture"]["fast_sha256"] != BODY_SHA
            or report["fixture"]["slow_sha256"] != BODY_SHA
            or report["alpn"] != "h2"):
        print("ORACLE_RESULT=INVALID_FIXTURE", file=sys.stderr)
        return 2
    streams = list(report["streams"].values())
    fast = next((row for row in streams if row["path"] == "/fast"), None)
    slow = next((row for row in streams if row["path"] == "/slow"), None)
    if not fast or not slow or fast["bytes_sent"] != FULL or not fast["finished"]:
        print("ORACLE_RESULT=INVALID_FAST_CONTROL", file=sys.stderr)
        return 2
    output = args.client_log.read_text(errors="replace")
    progress = [int(match.group(1)) for line in output.splitlines()
                if (match := re.search(r"PROGRESS recvd1=\d+ recvd2=(\d+)", line))]
    completed = (
        "finished download of 'https://localhost:18755/slow'; "
        "curl status = 0, body = 16777216d bytes"
    ) in output
    print(f"ORACLE_TARGET_SLOW_BYTES={slow['bytes_sent']}")
    print(f"ORACLE_PEER_WINDOW={slow['final_peer_window']}")
    print(f"ORACLE_STREAM_WINDOW_UPDATES={slow['window_updates']}")
    if (args.client_rc == 124 and not completed
            and slow["bytes_sent"] == STALLED
            and slow["final_peer_window"] == 0
            and slow["window_updates"] == 1
            and progress[-5:] == [STALLED] * 5):
        print("ORACLE_RESULT=WINDOW_STALL_10M_ZERO_WINDOW_NO_UPDATE")
        return 1
    if (args.client_rc == 0 and completed
            and slow["bytes_sent"] == FULL
            and slow["window_updates"] >= 2):
        print("ORACLE_RESULT=FULL_16M_RESPONSE")
        return 0
    print("ORACLE_RESULT=UNCLASSIFIED", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
