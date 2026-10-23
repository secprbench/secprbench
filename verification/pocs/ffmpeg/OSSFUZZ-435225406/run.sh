#!/bin/sh
# Reproducer for OSSFUZZ-435225406 (VVC palette escape-value integer overflow).
#
# ff_vvc_palette_escape_val() can return a negative AVERROR value on a
# malformed bitstream. In the introduced/buggy revision, palette_subblock_data()
# (libavcodec/vvc/ctu.c) multiplies that value by `scale` before checking for
# the error, causing signed integer overflow.
#
# This harness pulls in the *actual*, unmodified libavcodec/vvc/ctu.c
# translation unit (via #include) so the real static palette_subblock_data()
# function executes, and drives it with a real VVC CABAC bypass decoder
# (ff_init_cabac_decoder + get_cabac_bypass) fed an all-0xFF buffer. That
# buffer makes the CABAC bypass decoder yield a run of leading '1' bits,
# which drives the k-th order Exp-Golomb decoder used for the palette escape
# value out of its valid range, forcing ff_vvc_palette_escape_val() to return
# an AVERROR sentinel. We build a minimal but real CodingUnit/TransformUnit/
# VVCSPS/etc. context (all zero/simple values) so a single escape-coded
# palette sample is decoded, exactly reaching the vulnerable multiply line.
#
# We compile our own harness with -fsanitize=address,undefined so the signed
# integer overflow in the real vulnerable line is caught, since this
# particular build of the target was not otherwise instrumented with UBSan.

set -e
cd /work

clang -fsanitize=address,undefined -fno-sanitize-recover=undefined \
    -fno-omit-frame-pointer -g -O0 \
    -I. -Ilibavutil -Ilibavcodec/vvc \
    /poc/harness.c -o /tmp/poc_harness \
    libavcodec/libavcodec.a libswresample/libswresample.a libavutil/libavutil.a \
    -lm -lpthread -latomic -lz

UBSAN_OPTIONS=print_stacktrace=1:halt_on_error=1 \
ASAN_OPTIONS=abort_on_error=1:detect_leaks=0 \
    /tmp/poc_harness
