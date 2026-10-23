#!/bin/sh
set -e
CC=${CC:-cc}
INCDIR=/work/include
LIBDIR=/work
$CC -g -O0 -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer \
    -I"$INCDIR" -I/work -o /tmp/poc /poc/poc.c -L"$LIBDIR" -lssl -lcrypto -lpthread -ldl
/tmp/poc
