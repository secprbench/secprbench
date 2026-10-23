#!/bin/bash
# This bug (OSSFUZZ-422217206) is a pure use-of-uninitialized-value on
# in-bounds heap memory (MemorySanitizer-class). The default verify build at
# /work is built with ASan only, which cannot observe this class of bug, so
# this script builds a dedicated, minimal MemorySanitizer build of the exact
# same checked-out source tree (no tracked files are modified) under /tmp,
# then compiles and runs poc.c against it. This is done fresh every
# invocation because the container/tmpfs is not persisted between calls.
set -e
rm -rf /tmp/msan-src
cp -a /work /tmp/msan-src
cd /tmp/msan-src
make distclean >/tmp/distclean.log 2>&1 || true

./configure --cc=clang --cxx=clang++ \
  --extra-cflags='-g -O1 -fsanitize=memory -fsanitize-memory-track-origins=2 -fno-omit-frame-pointer' \
  --extra-ldflags='-fsanitize=memory' \
  --enable-gpl --disable-stripping --disable-optimizations --disable-asm --disable-doc \
  --disable-avdevice --disable-network --disable-swscale \
  --disable-everything --enable-avcodec --enable-avformat --enable-avutil --enable-swresample \
  --enable-encoder=dxv --enable-decoder=rawvideo \
  --enable-muxer=avi --enable-muxer=null --enable-demuxer=rawvideo \
  --enable-protocol=file --enable-protocol=pipe \
  > /tmp/msan_configure.log 2>&1
echo "CONFIGURE_RET=$?"

make -j64 libavcodec/libavcodec.a libavformat/libavformat.a libavutil/libavutil.a \
          libswresample/libswresample.a libavfilter/libavfilter.a > /tmp/msan_build.log 2>&1
echo "MAKE_RET=$?"
tail -20 /tmp/msan_build.log

clang -g -O1 -fsanitize=memory -fsanitize-memory-track-origins=2 -fno-omit-frame-pointer \
  -I/tmp/msan-src /poc/poc.c \
  -L/tmp/msan-src/libavcodec -L/tmp/msan-src/libavformat -L/tmp/msan-src/libavutil \
  -L/tmp/msan-src/libswresample -L/tmp/msan-src/libavfilter \
  -Wl,--start-group -lavcodec -lavformat -lavutil -lswresample -lavfilter -Wl,--end-group \
  -lpthread -lm -lz -o /tmp/poc_msan
echo "COMPILE_DONE"

echo "=== RUN ==="
# abort_on_error=1 turns the MSan report into a real SIGABRT crash instead of
# a plain exit(1), so it registers unambiguously as a crash.
export MSAN_OPTIONS=abort_on_error=1:exitcode=134:halt_on_error=1
/tmp/poc_msan
echo "RUN_RET=$?"
