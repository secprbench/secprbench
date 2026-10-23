#!/bin/bash
# Build FFmpeg's own oss-fuzz harness (tools/target_dec_fuzzer.c) for
# AV_CODEC_ID_AAC_LATM against this revision's already-built libavcodec.a,
# then execute it once on the crafted reproducer input.
set -e
cd /work

if [ ! -x /work/aac_latm_fuzzer_run ]; then
  clang -g -O1 -fsanitize=address,fuzzer -fno-omit-frame-pointer \
    tools/target_dec_fuzzer.c -o /work/aac_latm_fuzzer_run -I. -I./fftools \
    -DFFMPEG_CODEC=AV_CODEC_ID_AAC_LATM -DFUZZ_FFMPEG_AUDIO \
    -Llibavcodec -Llibavdevice -Llibavfilter -Llibavformat -Llibavutil -Llibpostproc -Llibswscale -Llibswresample \
    -Wl,--as-needed -Wl,-z,noexecstack \
    -lavdevice -lavfilter -lavformat -lavcodec -lswresample -lswscale -lavutil -ldl -lm -lz -pthread
fi

cat /poc/crash_dq_part0.bin /poc/crash_dq_part1.bin /poc/crash_dq_part2.bin /poc/crash_dq_part3.bin > /tmp/crash_input.bin

ASAN_OPTIONS=detect_leaks=0 /work/aac_latm_fuzzer_run /tmp/crash_input.bin
