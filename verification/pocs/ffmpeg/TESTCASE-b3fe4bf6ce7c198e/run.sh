#!/bin/bash
# Harness-based reproducer (see harness_config.c / harness_frame.c for full
# rationale). Compiles and runs the real, unmodified target functions
# decode_usac_element_pair() and parse_mps212() (via source #include) with a
# crafted bitstream that sets bsOttBandsPhase=31 (> numBands=28), matching
# the documented root cause. On post_intro this reliably produces an
# AddressSanitizer stack-buffer-overflow inside ec_pair_dec(); pre-intro,
# parse_mps212()/AACUsacMPSData do not exist at all, so we fall back to the
# config-stage-only harness (which still shows the same unchecked field
# being stored, ret=0, with no consumer present); post-benign rejects the
# out-of-range value at the config stage before ever reaching parse_mps212.
set -u
cd /tmp

CC=clang
FLAGS="-g -O0 -fsanitize=address -fno-omit-frame-pointer -std=c17 -I/work -I/work/libavcodec -I/work/libavcodec/aac -Wno-everything"
LIBS="/work/libavcodec/libavcodec.a /work/libswresample/libswresample.a /work/libavutil/libavutil.a -lm -lz -latomic -pthread"

echo "=== Attempting harness_frame.c (config stage + parse_mps212 frame stage) ==="
if $CC $FLAGS /poc/harness_frame.c -o /tmp/hf $LIBS 2>/tmp/build_frame.log; then
    echo "=== Build OK: parse_mps212()/AACUsacMPSData are present in this revision ==="
    /tmp/hf
    exit $?
else
    echo "=== Build FAILED: parse_mps212()/AACUsacMPSData are absent in this revision ==="
    echo "--- compiler output (expected on pre-intro) ---"
    cat /tmp/build_frame.log
    echo "=== Falling back to harness_config_pre.c (config-stage only) ==="
    if $CC $FLAGS /poc/harness_config_pre.c -o /tmp/hc $LIBS 2>/tmp/build_config.log; then
        /tmp/hc
        exit $?
    else
        echo "--- harness_config_pre.c also failed to build ---"
        cat /tmp/build_config.log
        exit 1
    fi
fi
