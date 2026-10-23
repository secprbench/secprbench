#!/bin/sh
# Reproducer for OSSFUZZ-408304111 (signed integer overflow in
# yuv2rgba64_full_1_c_template, libswscale/output.c).
#
# The project's default build only enables ASan, which does not catch
# plain signed-integer-overflow UB. This script additionally compiles
# libswscale/output.c with -fsanitize=undefined (combined with the
# existing -fsanitize=address) so the introduced overflow can be
# observed, then links a small harness (poc.c) against the patched
# libswscale.a and runs it.
#
# Run from the FFmpeg source tree root (i.e. /work in the verification
# container).
set -e

CFLAGS_COMMON="-I. -I./ -D_ISOC11_SOURCE -D_FILE_OFFSET_BITS=64 -D_LARGEFILE_SOURCE -D_POSIX_C_SOURCE=200112 -D_XOPEN_SOURCE=600 -DPIC -I./compat/stdbit -DZLIB_CONST -DHAVE_AV_CONFIG_H -DBUILDING_swscale -g -O1 -fsanitize=address,undefined -fno-sanitize-recover=undefined -fno-omit-frame-pointer -std=c17 -fPIC -pthread -fno-math-errno -fno-signed-zeros -mstack-alignment=16 -Qunused-arguments"

clang $CFLAGS_COMMON -c -o libswscale/output.o libswscale/output.c
ar r libswscale/libswscale.a libswscale/output.o

clang -I. -I./ -DHAVE_AV_CONFIG_H -g -O1 -fsanitize=address,undefined \
  -fno-sanitize-recover=undefined -fno-omit-frame-pointer -Qunused-arguments \
  "$(dirname "$0")/poc.c" -o /tmp/poc_408304111 \
  -L./libswscale -L./libavutil -lswscale -lavutil -lm -lpthread

UBSAN_OPTIONS=print_stacktrace=1 ASAN_OPTIONS=detect_leaks=0 \
  /tmp/poc_408304111 2 32 32 32 32 1 9 1
