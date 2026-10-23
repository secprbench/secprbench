#!/bin/bash
# Deterministically generate a wasm-GC module whose global initializers
# allocate several large structs via `struct.new_default` in const-expr
# position, exceeding the default 512KiB GC heap capacity. This exercises
# the const-expr evaluator's fallible GC allocation path (StructNew /
# StructNewDefault) at instantiation time (global initialization), which is
# where the intro commit added a new reachable `Err` without changing the
# existing unconditional `.expect(...)` on `eval(...)`'s result.
set -eu

OUT=/tmp/poc_gc_oom.wat
python3 - "$OUT" <<'PYEOF'
import sys
out = sys.argv[1]
N_FIELDS = 10000      # validator max (MAX_WASM_STRUCT_FIELDS)
N_STRUCTS = 8         # 8 * 10000 * 8 bytes = 640,000 bytes > 512KiB default GC heap

lines = ["(module"]
field = "(field i64)" * N_FIELDS
for i in range(N_STRUCTS):
    lines.append(f"  (type $t{i} (struct {field}))")
for i in range(N_STRUCTS):
    lines.append(f"  (global $g{i} (ref null $t{i}) (struct.new_default $t{i}))")
lines.append(")")

with open(out, "w") as f:
    f.write("\n".join(lines))
    f.write("\n")
PYEOF

WT=/work/target/x86_64-unknown-linux-gnu/release/wasmtime
exec "$WT" run -W gc=y -W function-references=y "$OUT"
