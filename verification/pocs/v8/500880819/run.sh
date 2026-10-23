#!/usr/bin/env bash
set -euo pipefail
cd /work
exec ./out.gn/verify/d8 --allow-natives-syntax --maglev --expose-gc test/mjsunit/mjsunit.js "$INPUT"
