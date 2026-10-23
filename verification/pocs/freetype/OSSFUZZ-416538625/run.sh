#!/usr/bin/env bash
set -euo pipefail
target_root=${SECPRBENCH_TARGET_ROOT:-/work}
poc_root=${SECPRBENCH_POC_ROOT:-/poc}
oracle_output=${SECPRBENCH_ORACLE_OUTPUT:-/work/svg_alloc_oracle}
cd "$target_root"
clang -g -O1 -fsanitize=address,undefined -fno-sanitize-recover=all \
  -fno-omit-frame-pointer -I "$target_root/include" \
  -I "$target_root/build/include" "$poc_root/oracle.c" \
  "$target_root/build/libfreetype.a" -lm -lz -o "$oracle_output"
observed=$("$oracle_output" "$poc_root/svg-alloc.ttf")
printf '%s\n' "$observed"
case "$observed" in
  *'large_alloc_count=1 max_large_bytes=134217728'*)
    printf '%s\n' 'ORACLE_RESULT=VULNERABLE_128M_ALLOCATION_REQUEST'
    exit 1 ;;
  *'large_alloc_count=0 max_large_bytes=0'*)
    printf '%s\n' 'ORACLE_RESULT=NO_LARGE_ALLOCATION_REQUEST'
    exit 0 ;;
  *)
    printf '%s\n' 'ORACLE_RESULT=UNKNOWN' >&2
    exit 2 ;;
esac
