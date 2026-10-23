#!/bin/sh
set -e
cd /work
clang -g -O1 -fsanitize=address -fno-omit-frame-pointer -std=gnu11 \
    -I/work -I/work/libavutil -I/work/libavcodec \
    /poc/poc.c -o /tmp/poc \
    -Wl,--start-group \
    /work/libavcodec/libavcodec.a \
    /work/libswresample/libswresample.a \
    /work/libavutil/libavutil.a \
    -Wl,--end-group \
    -pthread -lm -latomic -lz -fsanitize=address
/tmp/poc
