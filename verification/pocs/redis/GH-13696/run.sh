#!/bin/bash
# DataRace repro for GH-13696 / fixed by 6ea4e2c949c7.
# Race: I/O thread calls lookupCommand()->dictFind() (reads dict->useStoredKeyApi)
# concurrently with the main thread's dictNext() safe-iterator rehash-pause
# bookkeeping (writes dict->pauserehash) on the same dict object, triggered by
# MODULE LOAD/UNLOAD of a module with subcommands while client traffic is being
# parsed by I/O threads (--io-threads 4 --io-threads-do-reads yes).
set -x
cd /work

# Ensure a ThreadSanitizer build (DataRace needs TSAN, not ASAN/UBSan).
if ! nm -D src/redis-server 2>/dev/null | grep -qi '__tsan_'; then
    ( cd src && make distclean >/tmp/distclean.log 2>&1 )
    make SANITIZER=thread -j"$(nproc)" >/tmp/tsan_build.log 2>&1 || {
        echo "TSAN build failed"; tail -n 80 /tmp/tsan_build.log; exit 2;
    }
fi

# Build a small test module with subcommands to load/unload repeatedly.
if [ ! -f tests/modules/basics.so ]; then
    ( cd tests/modules && make basics.so >/tmp/mod_build.log 2>&1 )
fi

rm -f /tmp/redis_tsan.log /tmp/tsan.*
export TSAN_OPTIONS="log_path=/tmp/tsan halt_on_error=0 history_size=7 second_deadlock_stack=1"

src/redis-server --port 7333 --daemonize no --io-threads 4 --io-threads-do-reads yes \
  --save "" --appendonly no --logfile /tmp/redis_tsan.log --loglevel notice &
SERVER_PID=$!
sleep 2
src/redis-cli -p 7333 ping

src/redis-benchmark -p 7333 -q -t set,get -n 300000 -c 50 -P 8 > /tmp/bench.log 2>&1 &
BENCH_PID=$!

for i in $(seq 1 400); do
  src/redis-cli -p 7333 module load /work/tests/modules/basics.so >/dev/null 2>&1
  src/redis-cli -p 7333 module unload basics >/dev/null 2>&1
done &
MODLOOP_PID=$!

for i in $(seq 1 400); do
  src/redis-cli -p 7333 command docs >/dev/null 2>&1
  src/redis-cli -p 7333 command count >/dev/null 2>&1
done &
CMDLOOP_PID=$!

wait $BENCH_PID
wait $MODLOOP_PID 2>/dev/null
wait $CMDLOOP_PID 2>/dev/null

sleep 1
kill $SERVER_PID 2>/dev/null
sleep 1

echo "=== tsan reports ==="
ls -la /tmp/tsan* 2>&1
FOUND=0
for f in /tmp/tsan.*; do
  [ -e "$f" ] || continue
  cat "$f"
  if grep -q "ThreadSanitizer: data race" "$f"; then
    FOUND=1
  fi
done

echo "=== server log tail ==="
tail -n 60 /tmp/redis_tsan.log

if [ "$FOUND" = "1" ]; then
  echo "RACE_DETECTED"
  exit 66
else
  echo "NO_RACE_DETECTED"
  exit 0
fi
