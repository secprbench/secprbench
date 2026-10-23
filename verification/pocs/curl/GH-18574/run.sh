#!/bin/sh
# Behavioral PoC for GH-18574 (TFTP timeout propagation logic bug).
# Start a UDP "black hole" listener that accepts but never answers TFTP
# packets, then issue a TFTP request with a short --connect-timeout while
# TFTP never leaves its initial state. The bug delays/alters the timeout
# abort path (see discussion.md / meta.json root_cause).
python3 -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(('127.0.0.1', 6969))
while True:
    data, addr = s.recvfrom(65536)
" &
LISTENER_PID=$!
sleep 1
time timeout 25 /work/src/curl -v --connect-timeout 3 tftp://127.0.0.1:6969/foo
CURL_EXIT=$?
kill $LISTENER_PID 2>/dev/null
echo "CURL_EXIT=$CURL_EXIT"
exit 0
