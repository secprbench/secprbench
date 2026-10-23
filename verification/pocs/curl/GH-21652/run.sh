#!/bin/sh
set -e
cd /tmp
gcc -g -O1 -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer \
  -I/work/include /poc/poc.c -o poc \
  /work/lib/.libs/libcurlu.a -lssl -lcrypto -lz -lpthread
./poc
