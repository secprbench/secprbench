#!/bin/sh
set -e
cp /poc/poc.c /tmp/poc.c
if [ -f /work/ext/misc/base64.c ]; then
  EXTRA_SRC=/work/ext/misc/base64.c
  DEFS="-DHAVE_BASE64=1"
else
  EXTRA_SRC=
  DEFS=""
fi
gcc -g -O1 -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer \
  -DSQLITE_CORE=1 -DSQLITE_OS_UNIX=1 -DSQLITE_ENABLE_MATH_FUNCTIONS -DSQLITE_HAVE_ZLIB=1 $DEFS \
  -I/work -I/work/src \
  -o /tmp/poc_bin /tmp/poc.c /work/sqlite3.c $EXTRA_SRC \
  -lm -lz -lpthread -ldl
/tmp/poc_bin
