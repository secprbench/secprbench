#!/bin/bash
# Build & run the white-box harness against the target revision checked out
# at /work, using /work's own build configuration (real CFLAGS) plus
# -fsanitize=signed-integer-overflow,shift so the addition at the heart of
# this task's root cause traps under UBSan. Uses the *same* synthetic
# coefficient (2147483640) on every revision; only the harness source
# (harness.c vs harness_pre.c) differs, matching each revision's own real
# function signature for dequantization_int_97().
set -e
cd /work

if grep -q 'dequantization_int_97(int x, int y, Jpeg2000Cblk \*cblk,' libavcodec/jpeg2000dec.c \
   && grep -A2 'static void dequantization_int_97' libavcodec/jpeg2000dec.c | grep -q 'const int M_b'; then
    SRC=/poc/harness.c
else
    SRC=/poc/harness_pre.c
fi
echo "Using harness: $SRC"

cp libavcodec/libavcodec.a /work/libavcodec_nodec.a
ar d /work/libavcodec_nodec.a jpeg2000dec.o

CFLAGS_COMMON="-I. -I./ -D_ISOC11_SOURCE -D_FILE_OFFSET_BITS=64 -D_LARGEFILE_SOURCE -D_POSIX_C_SOURCE=200112 -D_XOPEN_SOURCE=600 -DPIC -I./compat/stdbit -DZLIB_CONST -DHAVE_AV_CONFIG_H -DBUILDING_avcodec -g -O1 -fsanitize=address -fsanitize=signed-integer-overflow,shift -fno-sanitize-recover=signed-integer-overflow,shift -fno-omit-frame-pointer -std=c17 -fPIC -pthread -Qunused-arguments"

clang $CFLAGS_COMMON -c -o /work/harness_run.o "$SRC"

clang -g -O1 -fsanitize=address -fsanitize=signed-integer-overflow,shift -fno-omit-frame-pointer /work/harness_run.o \
  -o /work/harness_run_bin \
  /work/libavcodec_nodec.a ./libavutil/libavutil.a ./libswresample/libswresample.a \
  -pthread -lm -latomic -lz -Wl,--as-needed -Qunused-arguments

/work/harness_run_bin
