#!/bin/bash
# Build and run the Curl_get_line() read-error PoC against the target tree
# built at /work. Picks the right driver source depending on which
# Curl_get_line() signature this revision exposes (an orthogonal API
# refactor, unrelated to the bug), then compiles it directly against
# libcurl's static archive so we can call the internal function.
set -u
cd /work

HDR=lib/curl_get_line.h
if grep -q 'Curl_get_line(struct dynbuf \*buf, FILE \*input, bool \*eof)' "$HDR"; then
  SRC=/poc/poc_new.c
else
  SRC=/poc/poc_old.c
fi

LIBA=lib/.libs/libcurl.a
if [ ! -f "$LIBA" ]; then
  LIBA=$(find . -name 'libcurl.a' | head -1)
fi

gcc -g -O1 -fsanitize=address,undefined -fno-sanitize-recover=all \
    -fno-omit-frame-pointer -DHAVE_CONFIG_H -D_GNU_SOURCE -DBUILDING_LIBCURL \
    -I include -I lib -I . \
    "$SRC" -o /tmp/poc_get_line "$LIBA" -lssl -lcrypto -lz 2>&1
BUILD_STATUS=$?
if [ $BUILD_STATUS -ne 0 ]; then
  echo "BUILD_FAILED status=$BUILD_STATUS"
  exit 97
fi

timeout 10 /tmp/poc_get_line
echo "EXIT_CODE=$?"
