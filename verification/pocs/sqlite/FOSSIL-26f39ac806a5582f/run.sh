#!/bin/sh
set -e
cd /tmp
cp /work/sqlite3.c /work/sqlite3.h .
gcc -g -O1 -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer \
    -DSQLITE_ENABLE_FTS3 -DSQLITE_ENABLE_FTS4 \
    -I. /poc/poc.c sqlite3.c -ldl -lpthread -o poc_bin
./poc_bin
