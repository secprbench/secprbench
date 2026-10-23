#!/bin/sh
# Reproducer for GH-10387: wasi:http serve handler returns without calling
# response-outparam::set. On the introduced-bug revision this makes
# `wasmtime serve` panic in handle_request's `.expect_err(...)` call.
set -e
cd /work
BIN=target/x86_64-unknown-linux-gnu/release/wasmtime
PORT=18123
LOG=/tmp/serve_poc.log
rm -f "$LOG"

"$BIN" serve --addr 127.0.0.1:$PORT /poc/handle_noset.wat > "$LOG" 2>&1 &
SPID=$!

# wait for server to come up
for i in $(seq 1 20); do
  if grep -q "Serving HTTP" "$LOG" 2>/dev/null; then
    break
  fi
  sleep 0.25
done

curl -s -m 5 -o /tmp/resp_poc.txt -w "HTTP_CODE:%{http_code}\n" http://127.0.0.1:$PORT/ || true

sleep 1

echo "=== serve log ==="
cat "$LOG"

if grep -q "if the receiver has an error, the task must have failed" "$LOG"; then
  echo "POC_RESULT: PANIC_OBSERVED"
else
  echo "POC_RESULT: NO_PANIC"
fi

kill -9 $SPID 2>/dev/null || true
wait 2>/dev/null || true
