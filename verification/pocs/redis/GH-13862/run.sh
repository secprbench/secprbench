#!/bin/bash
set -x
bash /poc/build_fixed.sh > /tmp/build.log 2>&1
tail -3 /tmp/build.log

cd /tmp
PORT=7777
rm -f /tmp/dump.rdb /tmp/rsf.log
nohup /tmp/redis-server-fixed --port $PORT --daemonize no --save '' --dir /tmp --logfile /tmp/rsf.log > /tmp/rsf_stdout.log 2>&1 < /dev/null &
disown
SERVER_PID=$!

for i in $(seq 1 50); do
  /work/src/redis-cli -p $PORT ping 2>/dev/null | grep -q PONG && break
  sleep 0.2
done

/work/src/redis-cli -p $PORT flushall
/work/src/redis-cli -p $PORT set key value px 50
/work/src/redis-cli -p $PORT client pause 10000 write

# wait for key to be logically expired
sleep 0.3

echo "=== calling randomkey with 5s timeout ==="
timeout 5 /work/src/redis-cli -p $PORT randomkey
RC=$?
echo "randomkey exit code: $RC"
if [ $RC -eq 124 ]; then
  echo "RANDOMKEY_HUNG_INFINITE_LOOP"
else
  echo "RANDOMKEY_RETURNED_OK"
fi

# Best-effort cleanup; the server may be wedged in a busy loop if the bug
# reproduced, so never let cleanup itself hang the harness.
timeout 2 /work/src/redis-cli -p $PORT client unpause >/dev/null 2>&1
timeout 2 /work/src/redis-cli -p $PORT shutdown nosave >/dev/null 2>&1
sleep 0.3
pkill -9 -f redis-server-fixed 2>/dev/null
sleep 0.2
echo "---server log tail---"
tail -20 /tmp/rsf.log
exit 0
