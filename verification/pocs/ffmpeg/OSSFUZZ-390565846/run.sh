#!/bin/sh
set -e
cd /tmp
clang -g -O0 -fsanitize=address -std=c17 -I/work -I/work/libavcodec -I/work/libavutil \
  /poc/poc.c \
  /work/libavcodec/libavcodec.a /work/libswresample/libswresample.a /work/libavutil/libavutil.a \
  -lm -lpthread -latomic -lz -o /tmp/poc
export ASAN_OPTIONS=detect_leaks=0
exec /tmp/poc
