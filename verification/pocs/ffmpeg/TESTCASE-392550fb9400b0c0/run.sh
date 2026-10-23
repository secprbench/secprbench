#!/bin/bash
set -e
cd /work
clang -g -O0 -fsanitize=address -fno-omit-frame-pointer -I. -o /tmp/harness /poc/harness.c \
    -Llibavcodec -Llibavformat -Llibavutil -Llibswresample \
    -lavcodec -lavformat -lavutil -lswresample -lm -lz -pthread
cd /tmp
ASAN_OPTIONS=detect_leaks=0 ./harness /poc/extradata.bin /poc/frame.bin
echo "EXIT=$?"
