#!/bin/sh
# Self-checking reproducer for GH-19039 ("pop3: function could get the
# ->transfer field wrong").
#
# Scenario: fetch a specific POP3 message (RETR <id>, a multi-line /
# dot-terminated command) while CURLOPT_NOBODY is set (curl --head), so
# data->req.no_body starts TRUE. pop3_perform_command() computes the
# correct value from the actual outgoing command ("RETR" is multi-line,
# so the fresh no_body should become FALSE: a real body is coming).
# pop3->transfer is the ONLY thing that gates whether the arriving
# message content is captured or thrown away
# (lib/pop3.c pop3_state_command_resp(): `if(pop3->transfer ==
# PPTRANSFER_BODY)`).
#
# This script uses gdb to print, at that exact gate, both fields:
#   - data->req.no_body  (captured via a $dataptr convenience variable
#     set while `data` is still live at pop3_perform()'s entry, since
#     it is later optimized out of debug info at the gate itself)
#   - pop3->transfer
# plus the actual bytes curl delivered for the message body.
#
# Correct/consistent state: no_body and transfer must agree about
# whether a body exists. The introduced bug makes them disagree
# (no_body says "body expected" while transfer still says "no body",
# because transfer was decided from the OLD/stale no_body before
# pop3_perform_command() recomputed it) -- and the real message content
# is silently dropped as a result.

python3 /poc/pop3srv.py >/tmp/srv.log 2>&1 </dev/null &
SRV_PID=$!
disown "$SRV_PID" 2>/dev/null
sleep 1

CONSUME_LINE=$(grep -n 'pop3->transfer == PPTRANSFER_BODY' /work/lib/pop3.c | head -1 | cut -d: -f1)

cat > /tmp/gdbcmds.txt <<EOF
set pagination off
break pop3_perform
run --head -u user:pass --max-time 8 -o /tmp/curl.out pop3://127.0.0.1:8110/1
set \$dataptr = data
break pop3.c:$CONSUME_LINE
continue
printf "MARKER no_body=%d transfer=%d\n", (int)((struct Curl_easy *)\$dataptr)->req.no_body, (int)pop3->transfer
continue
quit
EOF

gdb -q -batch -x /tmp/gdbcmds.txt /work/src/curl >/tmp/gdb.out 2>&1

kill -9 "$SRV_PID" 2>/dev/null

echo "$(grep '^MARKER' /tmp/gdb.out)"
echo "BODY_BYTES=$(wc -c < /tmp/curl.out)"
echo "BODY_CONTENT_BEGIN"
cat /tmp/curl.out
echo ""
echo "BODY_CONTENT_END"
exit 0
