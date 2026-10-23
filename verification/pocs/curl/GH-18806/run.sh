#!/bin/bash
# Data race (GH-18806) reproducer.
#
# The harness's default build of /work is configured with
# -fsanitize=address,undefined (see config.log), but this bug is a data
# race that only ThreadSanitizer can reliably detect. Linking a TSan poc
# against an ASan-built libcurl.a fails at link time (unresolved __asan_*
# symbols) on every revision identically, which is a harness/tooling
# mismatch, not evidence about the bug. So this script rebuilds libcurl
# from the *same, unmodified* /work source tree (copied aside, standard
# autotools configure/make, no source edits) with -fsanitize=thread, then
# links and runs the existing PoC (/poc/poc.c, /poc/server.c) against that
# TSan-instrumented library.
set -x
set -o pipefail

rm -rf /tmp/tsanbuild
mkdir -p /tmp/tsanbuild
cp -r /work /tmp/tsanbuild/src
cd /tmp/tsanbuild/src

make distclean >/tmp/distclean.log 2>&1

./configure --with-openssl --without-libpsl --disable-shared \
  CFLAGS="-g -O1 -fsanitize=thread -fno-omit-frame-pointer" \
  LDFLAGS="-fsanitize=thread" CC=clang > /tmp/configure.log 2>&1
CONFIGURE_RC=$?
if [ $CONFIGURE_RC -ne 0 ]; then
  echo "CONFIGURE FAILED"
  tail -60 /tmp/configure.log
  exit 1
fi

make -j"$(nproc)" -C lib > /tmp/make.log 2>&1
MAKE_RC=$?
if [ $MAKE_RC -ne 0 ]; then
  echo "LIBRARY BUILD FAILED"
  tail -80 /tmp/make.log
  exit 1
fi

CERT=/tmp/tsanbuild/src/tests/certs/Server-localhost-sv.pem
KEY=/tmp/tsanbuild/src/tests/certs/Server-localhost-sv.key
PORT=8444

clang -g -O0 -o /tmp/server /poc/server.c -lssl -lcrypto
/tmp/server $PORT $CERT $KEY &
SRV_PID=$!
sleep 1

clang -g -O1 -fsanitize=thread -fno-omit-frame-pointer \
  -I/tmp/tsanbuild/src/include -o /tmp/poc /poc/poc.c \
  /tmp/tsanbuild/src/lib/.libs/libcurl.a -lpthread -lssl -lcrypto -lz 2>/tmp/poc_build.log
BUILD_RC=$?
cat /tmp/poc_build.log
if [ $BUILD_RC -ne 0 ]; then
  echo "POC BUILD FAILED"
  kill $SRV_PID 2>/dev/null
  exit 1
fi

TSAN_OPTIONS="halt_on_error=1:exitcode=66" /tmp/poc "https://127.0.0.1:$PORT/" 2>&1
RC=$?
kill $SRV_PID 2>/dev/null
wait $SRV_PID 2>/dev/null
echo "POC_EXIT=$RC"
exit $RC
