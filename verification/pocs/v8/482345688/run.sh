#!/bin/bash
set -u
D8="/work/out.gn/verify/d8"
if [ ! -x "$D8" ]; then
  D8="$(find /work -maxdepth 4 -iname d8 -type f 2>/dev/null | head -1)"
fi
cd /work
exec "$D8" \
  --turbo-fast-api-calls --expose-fast-api --no-liftoff --wasm-fast-api \
  --wasm-lazy-compilation --no-wasm-native-module-cache \
  --expose-gc --dump-counters --allow-natives-syntax \
  /poc/poc.js
