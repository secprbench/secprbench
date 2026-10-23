#!/bin/sh
# GH-27272 reproducer: drive the real internal extension-processing
# entry points (tls_collect_extensions / tls_parse_all_extensions) on a
# genuine SSL_CONNECTION with s->session == NULL, exactly reproducing the
# precondition documented by the fix commit for final_maxfragmentlen().
set -e
cd /work
clang -g -O0 -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer \
  -I. -Iinclude -Issl -Issl/statem -Icrypto \
  -DOPENSSL_USE_NODELETE -DL_ENDIAN -DOPENSSL_PIC -DOPENSSL_BUILDING_OPENSSL -DNDEBUG \
  -o /tmp/gh27272_poc /poc/poc.c libssl.a libcrypto.a -lpthread -ldl
ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 /tmp/gh27272_poc
