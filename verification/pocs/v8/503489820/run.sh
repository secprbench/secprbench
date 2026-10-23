#!/usr/bin/env bash
set -euo pipefail
cd /work
exec ./out.gn/verify/d8 --allow-natives-syntax --turbofan --wasm-deopt --wasm-inlining --liftoff --trace-deopt-verbose --trace-wasm-inlining "$INPUT"
