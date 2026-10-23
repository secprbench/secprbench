#!/usr/bin/env bash
# Simulate a broken replication link during diskless full sync, exactly
# while the replica is reading the HFE min-expire-time field of a
# RDB_TYPE_HASH_METADATA key (added by GH-14143 / dcf02298110f).
set -u
WORK=${1:-/work}
MPORT=10101
RPORT=10102
WORKDIR=$(mktemp -d)
LOG="$WORKDIR/replica.log"

python3 /poc/fake_master.py $MPORT &
MPID=$!
sleep 0.5

cat > "$WORKDIR/redis.conf" <<CONF
port $RPORT
daemonize no
logfile ""
dir $WORKDIR
save ""
appendonly no
repl-diskless-load swapdb
CONF

"$WORK/src/redis-server" "$WORKDIR/redis.conf" --logfile "$LOG" &
RPID=$!
sleep 1

"$WORK/src/redis-cli" -p $RPORT replicaof 127.0.0.1 $MPORT >/dev/null 2>&1
sleep 4

echo "=== SUMMARY ==="
if kill -0 $RPID 2>/dev/null; then
    echo "REPLICA_ALIVE=yes"
else
    echo "REPLICA_ALIVE=no"
fi

echo -n "PING_RESULT="
"$WORK/src/redis-cli" -p $RPORT -t 2 ping 2>&1

echo "MINEXPIRE_LOG_LINE: $(grep -o 'Internal error in RDB.*minExpire[^$]*' "$LOG" 2>/dev/null | head -1)"
echo "TERMINATE_LOG_LINE: $(grep -o 'Terminating server after rdb file reading failure\.' "$LOG" 2>/dev/null | head -1)"

kill -9 $RPID $MPID >/dev/null 2>&1
wait >/dev/null 2>&1
exit 0
