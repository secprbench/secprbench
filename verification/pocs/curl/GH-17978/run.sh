#!/bin/sh
# Reproduce GH-17978: tool_read_cb NULL deref when reading stdin for a
# telnet:// transfer that has no upload file (-T) configured.
#
# A plain TCP listener accepts the connection and keeps it open (does not
# send/close anything). curl's telnet handler then polls stdin via the
# CURLOPT_READFUNCTION callback (tool_read_cb) on every event-loop
# iteration while the connection is alive; -m 2 bounds the run. Reaching
# that callback with no -T/upload-file configured (per->uploadfile == NULL)
# is exactly what the intro commit made unsafe: it unconditionally does
# strcmp(per->uploadfile, ".") before checking per->uploadfile for NULL.
set -x
export UBSAN_OPTIONS=halt_on_error=1:abort_on_error=1:print_stacktrace=1
export ASAN_OPTIONS=halt_on_error=1:abort_on_error=1

CURL_BIN=/work/src/curl
[ -x "$CURL_BIN" ] || CURL_BIN=curl

PORT=$((20000 + ($$ % 20000)))
NCPID=""
i=0
while [ $i -lt 8 ]; do
  nc -l 127.0.0.1 $PORT >/tmp/ncout.log 2>&1 &
  NCPID=$!
  sleep 0.3
  if kill -0 $NCPID 2>/dev/null; then
    break
  fi
  PORT=$((PORT + 1))
  i=$((i + 1))
done

"$CURL_BIN" -fsm 2 telnet://127.0.0.1:$PORT < /poc/input.txt
RC=$?
echo "curl exit code: $RC"

kill $NCPID >/dev/null 2>&1
wait $NCPID 2>/dev/null

exit $RC
