#!/bin/sh
# Reproducer for GH-19438 (curl RTMP double-free on URL parse error).
#
# This container's curl has no librtmp -dev headers (only the runtime
# librtmp.so.1), so a plain `curl rtmp://...` never reaches
# lib/curl_rtmp.c (it compiles to an empty translation unit without
# USE_LIBRTMP). This script instead #includes the real, unmodified
# lib/curl_rtmp.c for whichever revision is checked out at /work, against
# a tiny stand-in <librtmp/rtmp.h> (/poc/rtmp_stub.h), and drives
# rtmp_setup_connection() through a simulated URL-parse failure the same
# way for every revision, then performs that revision's own connection
# teardown path.
#
# - Revisions using the connection meta-hash (CURL_META_RTMP_CONN, i.e.
#   post_intro and post_benign) use harness_postintro.c and link against
#   the real, already-built lib/hash.c object so Curl_conn_meta_set/get/
#   remove hit the project's genuine Curl_hash implementation.
# - The older revision (pre_intro), which still frees via
#   conn->proto.rtmp / rtmp_disconnect(), uses harness_preintro.c.
#
# RTMP_Free() in both harnesses calls the real libc free(); if
# lib/curl_rtmp.c frees the same RTMP* twice, AddressSanitizer aborts with
# a double-free report (a real crash), exactly like the full curl binary
# would if RTMP support were compiled in.
set -e

mkdir -p /tmp/inc/librtmp
cp /poc/rtmp_stub.h /tmp/inc/librtmp/rtmp.h
cd /work/lib

CFLAGS="-DHAVE_CONFIG_H -I../include -I. -I/tmp/inc -DBUILDING_LIBCURL \
  -g -O1 -fsanitize=address,undefined -fno-sanitize-recover=all \
  -fno-omit-frame-pointer -Wno-system-headers -D_GNU_SOURCE"

if grep -q "CURL_META_RTMP_CONN" curl_rtmp.c; then
  echo "[run.sh] using post-refactor (meta-hash) harness"
  gcc $CFLAGS -c /poc/harness_postintro.c -o /tmp/harness.o
  gcc -g -O1 -fsanitize=address,undefined -fno-sanitize-recover=all \
    -fno-omit-frame-pointer /tmp/harness.o libcurl_la-hash.o \
    -o /tmp/harness_run
else
  echo "[run.sh] using pre-refactor (conn->proto.rtmp) harness"
  gcc $CFLAGS -c /poc/harness_preintro.c -o /tmp/harness.o
  gcc -g -O1 -fsanitize=address,undefined -fno-sanitize-recover=all \
    -fno-omit-frame-pointer /tmp/harness.o -o /tmp/harness_run
fi

exec /tmp/harness_run
