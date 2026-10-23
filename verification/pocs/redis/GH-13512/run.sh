#!/bin/bash
cd /work
PORT=7799
rm -f /tmp/dump.rdb
./src/redis-server --port $PORT --daemonize no --save "" --dir /tmp &
SRV_PID=$!

# wait for server to come up
for i in $(seq 1 50); do
  ./src/redis-cli -p $PORT ping >/dev/null 2>&1 && break
  sleep 0.2
done

# Client 2: block on BRPOP mylist (background, separate connection)
./src/redis-cli -p $PORT brpop mylist 0 &
BRPOP_PID=$!

sleep 0.5

# Client 1: enable CLIENT NO-TOUCH then RPUSH on SAME connection
./src/redis-cli -p $PORT <<'EOF'
CLIENT NO-TOUCH on
RPUSH mylist elem1
EOF

sleep 1

wait $BRPOP_PID 2>/dev/null

if kill -0 $SRV_PID 2>/dev/null; then
    echo "SERVER_ALIVE"
    kill $SRV_PID 2>/dev/null
    wait $SRV_PID 2>/dev/null
    exit 0
else
    echo "SERVER_DEAD"
    wait $SRV_PID
    SRV_EXIT=$?
    echo "SRV_EXIT=$SRV_EXIT"
    exit 1
fi
