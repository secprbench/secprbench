#!/bin/bash
set -euo pipefail

probe_root="$(mktemp -d /tmp/secprbench-redis-14134.XXXXXX)"
trap 'rm -rf "$probe_root"' EXIT
python3 /poc/run_socket_oracle.py \
  --request /poc/malformed_get.resp \
  --output "$probe_root/run" \
  --binary current /work/src/redis-server
cat "$probe_root/run/current_server.log"
python3 - "$probe_root/run/results.json" <<'PY'
import json
import sys

result = json.load(open(sys.argv[1]))["results"][0]
print("REDIS_CHILD_EXIT=" + str(result["exit_after_request"]), flush=True)
print("REDIS_ORACLE=" + result["outcome"], flush=True)
if result["outcome"] == "normal_arity_error":
    raise SystemExit(0)
if result["outcome"] == "production_serverPanic_SIGABRT":
    # The Redis child itself exited on SIGABRT. Preserve that standard shell
    # status for the verifier; this is not a harness-generated signal.
    raise SystemExit(134)
raise SystemExit(2)
PY
