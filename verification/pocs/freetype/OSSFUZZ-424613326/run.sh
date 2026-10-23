#!/usr/bin/env bash
set -euo pipefail
target_root=${SECPRBENCH_TARGET_ROOT:-/work}
poc_root=${SECPRBENCH_POC_ROOT:-/poc}
oracle_output=${SECPRBENCH_ORACLE_OUTPUT:-/work/dfont_directory_oracle}
cd "$target_root"
clang -g -O1 -fsanitize=address,undefined -fno-sanitize-recover=all \
  -fno-omit-frame-pointer -I "$target_root/include" \
  -I "$target_root/build/include" "$poc_root/oracle.c" \
  "$target_root/build/libfreetype.a" -lm -lz -o "$oracle_output"
export ASAN_OPTIONS=detect_leaks=0:halt_on_error=1:abort_on_error=0
exec "$oracle_output" "$poc_root/two-sfnt.bin"
