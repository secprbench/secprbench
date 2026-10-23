#!/bin/bash
# Reproducer for OSSFUZZ-504281984 (ffmpeg dts2pts HEVC bsf AVTree invariant
# violation on selective dec_poc).
#
# Builds a small harness (poc.c) directly against the target's own
# libavcodec/libavutil/libswresample object archives from /work, and drives
# the real dts2pts bitstream filter (ff_dts2pts_bsf) through the public
# AVBSFContext send/receive API -- the same API tools/target_bsf_fuzzer.c
# uses -- feeding it a syntactically valid minimal HEVC Annex-B elementary
# stream (VPS/SPS/PPS + a long sequence of slices) built with the real CBS
# writer. The frame POC pattern (in crash_seq.txt) was found by randomized
# search over (nal_unit_type, slice_pic_order_cnt_lsb) sequences and
# reliably reaches the corrupted-AVTree code path in hevc_queue_frame().
set -e
cd /work

SEQ="$(cat /poc/crash_seq.txt)"

clang -g -O0 -fsanitize=address -fno-omit-frame-pointer \
    -I. -I./libavutil -I./libavcodec \
    /poc/poc.c -o /tmp/dts2pts_poc \
    libavcodec/libavcodec.a libswresample/libswresample.a libavutil/libavutil.a \
    -lm -lpthread -ldl -lz

ASAN_OPTIONS="${ASAN_OPTIONS:-detect_leaks=0:abort_on_error=1}" \
POC_LOGLEVEL="${POC_LOGLEVEL:-16}" \
    /tmp/dts2pts_poc "$SEQ"
