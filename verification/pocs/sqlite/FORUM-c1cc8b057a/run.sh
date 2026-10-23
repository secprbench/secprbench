#!/bin/sh
set -e
cd /tmp
cp /poc/poc.c .
cc -fsanitize=address,undefined -fno-sanitize-recover=all -g -O0 -DSQLITE_DEFAULT_MEMSTATUS=0 -I/work -o poctest poc.c /work/sqlite3.c -lm -ldl -lpthread
./poctest
