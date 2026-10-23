#!/bin/bash
cd /work
PORT=7799
rm -f /tmp/redis_poc.log
./src/redis-server --port $PORT --daemonize no --save '' --appendonly no \
    --logfile /tmp/redis_poc.log &
SRV_PID=$!

for i in $(seq 1 50); do
    if grep -q "Ready to accept" /tmp/redis_poc.log 2>/dev/null; then
        break
    fi
    sleep 0.2
done

python3 /poc/poc.py $PORT
PYRC=$?

sleep 0.5

if kill -0 $SRV_PID 2>/dev/null; then
    echo "SERVER_STILL_ALIVE (poc rc=$PYRC)"
    kill -9 $SRV_PID 2>/dev/null
    wait $SRV_PID 2>/dev/null
    echo "---- redis log ----"
    cat /tmp/redis_poc.log
    exit 0
else
    echo "SERVER_DIED (poc rc=$PYRC)"
    wait $SRV_PID
    SRVRC=$?
    echo "---- redis log ----"
    cat /tmp/redis_poc.log
    echo "server exit status: $SRVRC"
    exit $SRVRC
fi
