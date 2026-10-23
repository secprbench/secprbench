#!/bin/bash
# Reproducer for GH-18995 (double free of conn_to_host.encalloc on connection reuse).
# Requires the target curl binary to have been rebuilt with libidn2 support
# (see /work/.idn2shim) so that Curl_idnconvert_hostname() allocates host->encalloc.
set -x
cat > /tmp/server.py <<'EOF'
import http.server
import socketserver
import os

class Handler(http.server.SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

if __name__ == "__main__":
    os.chdir("/tmp/www")
    srv = Server(("127.0.0.1", 8099), Handler)
    srv.serve_forever()
EOF
mkdir -p /tmp/www
echo "hello world" > /tmp/www/index.html
python3 /tmp/server.py &
SERVERPID=$!
sleep 1

HOST2=$'caf\xc3\xa9.example'
LC_ALL=C.UTF-8 ASAN_OPTIONS=abort_on_error=1:detect_leaks=0:allocator_may_return_null=1 /work/src/curl -sv \
  --connect-to "orig.example:8099:${HOST2}:8099" \
  --resolve "xn--caf-dma.example:8099:127.0.0.1" \
  http://orig.example:8099/ http://orig.example:8099/
CURL_EXIT=$?

kill "$SERVERPID" 2>/dev/null
wait "$SERVERPID" 2>/dev/null
echo "CURL_EXIT=$CURL_EXIT"
exit $CURL_EXIT
