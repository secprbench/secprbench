#!/bin/sh
set -e
cd /work
cc -g -O1 -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer \
   -DSQLITE_ENABLE_PREUPDATE_HOOK -I. -o /tmp/poc /poc/poc.c sqlite3.c -ldl -lpthread
ASAN_OPTIONS=abort_on_error=1:detect_leaks=0 /tmp/poc
