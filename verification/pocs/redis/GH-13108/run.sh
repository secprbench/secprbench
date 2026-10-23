#!/bin/bash
set -u
cd /work
rm -f /tmp/redis.log /tmp/gdb.log /tmp/eval.log

cat > /tmp/inject.gdb <<'EOF'
set pagination off
set confirm off
break activeDefragCycle if $_caller_is("whileBlockedCron")
commands
silent
python
try:
    frame = gdb.newest_frame()
    caller = frame.older()
    f = caller
    target = None
    while f is not None:
        if f.name() == "evalGenericCommand":
            target = f
            break
        f = f.older()
    if target is not None:
        addr = int(target.read_var("l"))
        print("INJECT_FREE addr=0x%x" % addr)
        gdb.parse_and_eval("(void)free((void*)%d)" % addr)
        print("INJECT_FREE_DONE")
    else:
        print("NOTE_NO_EVALGENERIC_FRAME")
except Exception as e:
    print("INJECT_ERROR %s" % e)
end
disable 1
continue
end
run
EOF

nohup gdb -batch -x /tmp/inject.gdb \
    --args ./src/redis-server --port 7811 --daemonize no --logfile /tmp/redis.log --busy-reply-threshold 100 \
    > /tmp/gdb.log 2>&1 < /dev/null &
GDB_PID=$!
disown

for i in 1 2 3 4 5 6 7 8; do
    grep -q "Ready to accept" /tmp/redis.log 2>/dev/null && break
    sleep 0.5
done
echo "server_ready_lines=$(grep -c 'Ready to accept' /tmp/redis.log 2>/dev/null)"

./src/redis-cli -p 7811 config set busy-reply-threshold 100

timeout 15 ./src/redis-cli -p 7811 eval \
    "local i=0 while i<500000000 do i=i+1 end return i" 0 \
    > /tmp/eval.log 2>&1
echo "eval_exit=$?"
echo "=== eval.log ==="
cat /tmp/eval.log

sleep 1
echo "=== gdb log ==="
cat /tmp/gdb.log
echo "=== redis server log tail ==="
tail -80 /tmp/redis.log

if grep -q "AddressSanitizer\|ERROR: LeakSanitizer\|UndefinedBehaviorSanitizer\|runtime error:" /tmp/gdb.log 2>/dev/null; then
    echo "CRASH_DETECTED=1"
    kill -9 "$GDB_PID" 2>/dev/null
    pkill -9 -f "redis-server --port 7811" 2>/dev/null
    exit 134
fi
echo "CRASH_DETECTED=0"
kill -9 "$GDB_PID" 2>/dev/null
pkill -9 -f "redis-server --port 7811" 2>/dev/null
exit 0
