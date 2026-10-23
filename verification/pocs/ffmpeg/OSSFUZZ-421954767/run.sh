#!/bin/bash
# Regenerate the crafted Shorten PoC (see gen_poc.py). Prefer the
# MemorySanitizer-instrumented scratch build + driver (built separately
# under /work/_msan_src for this version, from an unmodified copy of the
# same checked-out source tree) since the bug is an MSAN-only
# use-of-uninitialized-value that AddressSanitizer cannot detect; fall
# back to the configured ASAN ffmpeg binary otherwise.
set -e
python3 /poc/gen_poc.py > /tmp/poc_shorten_input.bin
if [ -x /work/_msan_src/poc_driver ]; then
  export MSAN_OPTIONS=abort_on_error=1:exitcode=134
  exec /work/_msan_src/poc_driver /tmp/poc_shorten_input.bin
else
  exec /work/ffmpeg -f shn -i /tmp/poc_shorten_input.bin -f null -y /dev/null
fi
