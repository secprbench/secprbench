#!/usr/bin/env bash
set -Eeuo pipefail
cd /work
sha256sum -c /poc/checksums.txt >/dev/null
export LD_LIBRARY_PATH=/work/.verify-build/lib
export PYTHONPATH=/poc/h2_bundle.zip
export GH16955_SLOW_MIB=16 GH16955_PAUSE_KIB=1024 GH16955_RESUME_MS=50
export GH16955_PAUSE_LIMIT=1 GH16955_INITIAL_SPEED_KIB=0
export GH16955_CLEAR_SPEED_ON_RESUME=0 GH16955_TLS=1

test -s /work/.verify-build/lib/libcurl.so
/work/.verify-build/src/curl -V > /work/.verify-gh16955-version.txt
grep -q 'nghttp2/1.64.0' /work/.verify-gh16955-version.txt
g++ -std=c++20 -O1 -g -pthread -fsanitize=address,undefined \
  -fno-sanitize-recover=all -fno-omit-frame-pointer \
  -I /work/include /poc/reporter_adapted.cc \
  -L /work/.verify-build/lib -Wl,-rpath,/work/.verify-build/lib \
  -lcurl -o /work/.verify-gh16955-client

rm -f /work/.verify-gh16955-ready.json /work/.verify-gh16955-report.json
python3 /poc/http2_pause_server.py \
  --ready /work/.verify-gh16955-ready.json \
  --report /work/.verify-gh16955-report.json \
  --timeout 32 --fast-mib 16 --slow-mib 16 \
  --tls-cert /poc/localhost.crt --tls-key /poc/localhost.key \
  > /work/.verify-gh16955-server.log 2>&1 &
server_pid=$!
cleanup() {
  kill "$server_pid" 2>/dev/null || true
  wait "$server_pid" 2>/dev/null || true
}
trap cleanup EXIT
for _ in $(seq 1 100); do
  test -s /work/.verify-gh16955-ready.json && break
  kill -0 "$server_pid" 2>/dev/null || break
  sleep 0.05
done
if ! test -s /work/.verify-gh16955-ready.json; then
  echo ORACLE_RESULT=SERVER_NOT_READY >&2
  exit 2
fi

set +e
timeout --signal=TERM --kill-after=2s 27s /work/.verify-gh16955-client \
  > /work/.verify-gh16955-client.log 2>&1
client_rc=$?
set -e
wait "$server_pid" || true
test -s /work/.verify-gh16955-report.json || {
  echo ORACLE_RESULT=NO_SERVER_REPORT >&2
  exit 2
}
python3 /poc/classify.py --spec /poc/input.poc \
  --report /work/.verify-gh16955-report.json \
  --client-log /work/.verify-gh16955-client.log --client-rc "$client_rc"
