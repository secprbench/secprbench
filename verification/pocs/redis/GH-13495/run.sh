#!/usr/bin/env bash
cd /work
BIN=./src/redis-server
CLI=./src/redis-cli

MPORT=7700
RPORT=7701
MDIR=/tmp/m_$$
RDIR=/tmp/r_$$
mkdir -p "$MDIR" "$RDIR"

# Start master
$BIN --port $MPORT --daemonize no --save '' --dir "$MDIR" \
  --repl-diskless-sync yes --repl-diskless-sync-delay 0 \
  --logfile "$MDIR/log.txt" &
MPID=$!

# Start replica
$BIN --port $RPORT --daemonize no --save '' --dir "$RDIR" \
  --repl-diskless-load on-empty-db --replica-lazy-flush no \
  --logfile "$RDIR/log.txt" &
RPID=$!

sleep 1

for i in $(seq 1 20); do
  $CLI -p $MPORT ping >/dev/null 2>&1 && break
  sleep 0.5
done
for i in $(seq 1 20); do
  $CLI -p $RPORT ping >/dev/null 2>&1 && break
  sleep 0.5
done

# Load a function library on master so the replicated RDB contains function data
$CLI -p $MPORT FUNCTION LOAD "#!lua name=mylib
redis.register_function('myfunc', function(keys, args) return 1 end)"
$CLI -p $MPORT SET foo bar

# Start replication
$CLI -p $RPORT REPLICAOF 127.0.0.1 $MPORT

REPLICA_DIED=0
for i in $(seq 1 60); do
  if ! kill -0 $RPID 2>/dev/null; then
    REPLICA_DIED=1
    break
  fi
  status=$($CLI -p $RPORT info replication 2>/dev/null | grep master_link_status)
  if echo "$status" | grep -q up; then
    break
  fi
  sleep 0.5
done

echo "---- replica log ----"
cat "$RDIR/log.txt"
echo "---- master log ----"
cat "$MDIR/log.txt"

kill -9 $MPID 2>/dev/null

if [ "$REPLICA_DIED" = "1" ]; then
  # Reap the replica to get its real exit status (ASan aborts -> SIGABRT)
  wait $RPID
  rc=$?
  echo "REPLICA PROCESS DIED rc=$rc"
  exit $rc
else
  kill -9 $RPID 2>/dev/null
  wait $RPID 2>/dev/null
  echo "REPLICA SURVIVED / SYNCED OK"
  exit 0
fi
