#!/bin/sh
set -e
cd /work
clang -g -O1 -fsanitize=address -fno-omit-frame-pointer -std=c17 -I. -I./libavcodec \
  /poc/poc.c -o /tmp/poc_run \
  libavcodec/libavcodec.a libavutil/libavutil.a libswresample/libswresample.a \
  -lm -lpthread -fsanitize=address
exec /tmp/poc_run
