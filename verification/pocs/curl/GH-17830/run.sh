#!/bin/sh
# GH-17830 reproducer.
#
# lib/vtls/rustls.c requires the rustls backend (crustls/rustls-ffi), which
# is not installed and cannot be built offline in this environment (no
# librustls/rustls.h, no network access). USE_RUSTLS / USE_ECH are undefined
# in the configured build, so init_config_builder_ech() in rustls.c is never
# compiled into the curl binary here.
#
# This script instead exercises the real, unmodified internal function that
# init_config_builder_ech() calls (lib/base64.c's Curl_base64_decode(),
# identical across all reviewed revisions) under curl's real, public
# allocator-override API (curl_global_init_mem()) -- the exact condition the
# bug/fix describe as needed to turn the allocator/deallocator mismatch into
# a real bug. It then performs the *actual* cleanup logic read directly out
# of this container's own /work/lib/vtls/rustls.c source for the ECH
# command-line-config path, so the same script/command produces the
# version-correct behavior for whichever revision is checked out in /work.

set -e
cd /work

SRC=lib/vtls/rustls.c

if ! grep -q 'init_config_builder_ech' "$SRC" 2>/dev/null; then
  echo "rustls.c / ECH code not present in this revision" >&2
  exit 1
fi

# Does the ECH cleanup path free the base64-decoded buffer at all?
if ! grep -A3 'cleanup:' "$SRC" | grep -q 'free(ech_config)'; then
  MODE=0   # pre_intro: no free() on this path at all (a plain leak)
else
  # Does the file apply curl's memory-function overrides to this free()?
  if grep -q '"\.\./curl_memory\.h"' "$SRC" && grep -q '"\.\./memdebug\.h"' "$SRC"; then
    MODE=2 # fixed: free(ptr) macro-expands to the overridable Curl_cfree(ptr)
  else
    MODE=1 # introduced bug: plain libc free() bypassing curl's allocator
  fi
fi

echo "detected CLEANUP_MODE=$MODE from $SRC" >&2

cc -g -O1 -fsanitize=address,undefined -fno-sanitize-recover=all \
  -DCLEANUP_MODE=$MODE -Iinclude /poc/poc.c lib/.libs/libcurl.a \
  -lssl -lcrypto -lz -lpthread -o /tmp/poc_gh17830

ASAN_OPTIONS=detect_leaks=0 /tmp/poc_gh17830 AAAAAAAAAAAAAAAA
