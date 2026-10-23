#!/bin/bash
# Reproducer for OSSFUZZ-418421333 (cbs_apv_syntax_template.c tile() OOB read).
#
# This benchmark's source snapshot is incomplete: the real APV decoder
# (apv_dec.c) is not present, and configure does not auto-select
# CONFIG_CBS_APV, so cbs_apv.c / cbs_apv_syntax_template.c (present,
# unmodified, in the tree for post_intro/post_benign; absent for pre_intro)
# are not linked into the default libavcodec.a. We compile the existing,
# untouched source files directly (with -DCBS_APV=1, the same macro
# configure would otherwise define) and link them with a tiny harness
# (poc.c) that only calls the public CBS API to read then re-serialize a
# crafted APV bitstream, exactly exercising the tile() function named in
# meta.json's root cause.
set -e
cd /work

if [ ! -f libavcodec/cbs_apv.c ]; then
    echo "cbs_apv.c not present in this revision (pre-intro: feature not yet added)"
    echo "NO_CBS_APV_SOURCE"
    exit 0
fi

CFLAGS="-g -O1 -fsanitize=address -fno-omit-frame-pointer -I. -I./libavcodec -I./libavutil -include libavutil/internal.h -DCBS_APV=1"

clang $CFLAGS -c libavcodec/cbs_apv.c -o /tmp/cbs_apv.o
clang $CFLAGS -c libavcodec/cbs.c -o /tmp/cbs.o
clang -g -O1 -fsanitize=address -fno-omit-frame-pointer -I. -I./libavcodec -I./libavutil -c /poc/poc.c -o /tmp/poc.o

clang -g -O1 -fsanitize=address -fno-omit-frame-pointer /tmp/poc.o /tmp/cbs_apv.o /tmp/cbs.o -o /tmp/poc \
  -Llibavcodec -Llibavformat -Llibavutil -Llibswresample -Llibswscale -Llibavfilter -Llibavdevice -Llibpostproc \
  -lavcodec -lswresample -lavutil -pthread -lm -latomic -lz -fsanitize=address

INPUT_FILE="${INPUT:-/poc/input.apv}"
ASAN_OPTIONS=detect_leaks=0 /tmp/poc "$INPUT_FILE"
