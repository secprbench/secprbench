#!/bin/bash
cd /work || exit 1

if ! grep -rq "AV_CODEC_ID_ADPCM_N64" libavcodec/codec_id.h 2>/dev/null; then
  echo "RESULT:NO_DECODER_ENUM (AV_CODEC_ID_ADPCM_N64 absent in this revision - ADPCM_N64 decoder was not introduced yet)"
  exit 0
fi

mkdir -p /tmp/run
cp /poc/poc.c /tmp/run/poc.c

echo "== ASan run against the officially-built target libs (value-level check) =="
clang -g -O0 -fsanitize=address -I/work -c /tmp/run/poc.c -o /tmp/run/poc_asan.o 2>&1
clang -g -fsanitize=address /tmp/run/poc_asan.o /work/libavcodec/libavcodec.a /work/libswresample/libswresample.a /work/libavutil/libavutil.a -lm -lpthread -ldl -lz -o /tmp/run/poc_asan 2>&1
/tmp/run/poc_asan
echo "ASAN_EXIT:$?"

echo "== UBSan run: recompile the SAME unmodified adpcm.c from this revision =="
echo "== with -fsanitize=undefined added (target build only enables ASan), =="
echo "== swap into a copy of the prebuilt archive, relink, run =="
CFLAGS="-I. -I./ -D_ISOC11_SOURCE -D_FILE_OFFSET_BITS=64 -D_LARGEFILE_SOURCE -D_POSIX_C_SOURCE=200112 -D_XOPEN_SOURCE=600 -DPIC -I./compat/stdbit -DZLIB_CONST -DHAVE_AV_CONFIG_H -DBUILDING_avcodec -g -O1 -fsanitize=address,undefined -fno-sanitize-recover=undefined -fno-omit-frame-pointer -std=c17 -fPIC -pthread -Wno-everything -fno-math-errno -fno-signed-zeros -mstack-alignment=16 -Qunused-arguments"
clang $CFLAGS -c -o /tmp/run/adpcm_ubsan.o libavcodec/adpcm.c 2>&1
cp libavcodec/libavcodec.a /tmp/run/libavcodec_ubsan.a
ar d /tmp/run/libavcodec_ubsan.a adpcm.o
ar r /tmp/run/libavcodec_ubsan.a /tmp/run/adpcm_ubsan.o
clang -g -O0 -fsanitize=address,undefined -I/work -c /tmp/run/poc.c -o /tmp/run/poc_ubsan.o 2>&1
clang -g -fsanitize=address,undefined /tmp/run/poc_ubsan.o /tmp/run/libavcodec_ubsan.a /work/libswresample/libswresample.a /work/libavutil/libavutil.a -lm -lpthread -ldl -lz -o /tmp/run/poc_ubsan 2>&1

/tmp/run/poc_ubsan
rc=$?
echo "UBSAN_EXIT:$rc"
exit $rc
