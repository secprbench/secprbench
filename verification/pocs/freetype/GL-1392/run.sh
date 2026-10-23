#!/bin/sh
set -e
INPUT_FILE="${INPUT:-/poc/crafted.ttf}"
clang -O1 -g -fsanitize=address -fno-omit-frame-pointer \
  -I /work/build/include -I /work/include \
  /poc/poc.c /work/build/libfreetype.a -lm -lz \
  -o /tmp/gl1392_poc
exec /tmp/gl1392_poc "$INPUT_FILE"
