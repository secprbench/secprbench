#!/bin/bash
cd /work
export UBSAN_OPTIONS=print_stacktrace=1:halt_on_error=0
export ASAN_OPTIONS=abort_on_error=0:detect_leaks=0:allocator_may_return_null=1:handle_segv=0:handle_sigbus=0:handle_sigfpe=0:handle_abort=0
PORT=16399
./src/redis-server --port $PORT --daemonize no --logfile /tmp/redis.log &
SERVER_PID=$!
for i in $(seq 1 30); do
  ./src/redis-cli -p $PORT ping >/dev/null 2>&1 && break
  sleep 0.2
done
./src/redis-cli -p $PORT eval 'return error({})' 0
./src/redis-cli -p $PORT shutdown nosave >/dev/null 2>&1
wait $SERVER_PID
RC=$?
cat /tmp/redis.log
exit $RC
