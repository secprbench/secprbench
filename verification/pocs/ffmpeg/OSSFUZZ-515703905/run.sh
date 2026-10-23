#!/bin/sh
# Reproducer for OSSFUZZ-515703905: compiles the unmodified target
# translation unit libavcodec/aac/aacdec_usac.c together with /poc/poc.c
# (which calls the real decode_tsd() directly with bitstream-derived
# parameters nb_tr_slots=31, nb_slots=64) and runs it under UBSan+ASan.
#
# decode_tsd() does not exist prior to the intro commit (the USAC MPS212
# temporal-shape decoding feature was introduced together with the bug), so
# we detect its presence in the target source and compile poc.c with
# -DHAVE_DECODE_TSD accordingly; poc.c supplies a harmless stand-in when the
# function is absent so the exact same driver builds and runs cleanly on
# every revision.
set -e
cd /work
if grep -q "static void decode_tsd" libavcodec/aac/aacdec_usac.c 2>/dev/null; then
  HAVE=1
else
  HAVE=0
fi
clang -fsanitize=address,undefined -fno-sanitize-recover=undefined -g -O0 \
  -I. -I./libavcodec -I./libavutil -DHAVE_AV_CONFIG_H -DHAVE_DECODE_TSD=$HAVE \
  /poc/poc.c -o /tmp/poc_bin \
  -L./libavcodec -L./libavformat -L./libavutil -L./libswresample \
  -lavcodec -lavformat -lavutil -lswresample -lm -lz -lpthread
exec /tmp/poc_bin
