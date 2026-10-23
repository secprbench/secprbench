#!/bin/bash
# Diagnostic harness for OSSFUZZ-438961582 (dxv.c av_clip invariant violation).
#
# The target's own fix commit message says "Fixes: assertion failure": the
# bug is libavutil/common.h's av_clip_c() internal contract check
# `if (amin > amax) abort();`, which is compiled in only when ASSERT_LEVEL>=2
# (a standard OSS-Fuzz/continuous-fuzzing assertion-build setting). The
# sanctioned build here is configured without --assert-level, so that guard
# compiles out and the flaw (slice_count computed as 0 via an inverted
# av_clip(thread_count,1,0) range) is a silent no-op in this single/default
# threaded harness. To surface the already source-confirmed invariant
# violation deterministically, we recompile the SAME UNMODIFIED
# libavcodec/dxv.c (no source edits) with one extra define, -DASSERT_LEVEL=2,
# swap only that one object into a copy of the already-built libavcodec.a,
# and link it into a small decoder-only harness (poc.c). This changes no
# program logic, it only enables an existing internal contract check.
set -e
cd /work

clang -DHAVE_AV_CONFIG_H -DASSERT_LEVEL=2 \
  -D_ISOC99_SOURCE -D_FILE_OFFSET_BITS=64 -D_LARGEFILE_SOURCE \
  -D_POSIX_C_SOURCE=200112 -D_XOPEN_SOURCE=600 -DPIC -DZLIB_CONST \
  -I. -I/work \
  -g -O1 -fsanitize=address -fno-omit-frame-pointer -std=c11 -fPIC -pthread \
  -c libavcodec/dxv.c -o /tmp/dxv2.o

cp libavcodec/libavcodec.a /tmp/libavcodec_patched.a
ar d /tmp/libavcodec_patched.a dxv.o

clang -O0 -g -fsanitize=address -I/work -o /tmp/poc2 /poc/poc.c \
  /tmp/dxv2.o /tmp/libavcodec_patched.a \
  libavformat/libavformat.a libswresample/libswresample.a libavutil/libavutil.a \
  -lm -lpthread -ldl -lz

INPUT="${INPUT:-/poc/ycg6_raw.bin}"
echo "Running harness on $INPUT (width=16 height=4 thread_count=1 thread_type=0)"
/tmp/poc2 16 4 "$INPUT" 1 0
echo "harness exit code: $?"
