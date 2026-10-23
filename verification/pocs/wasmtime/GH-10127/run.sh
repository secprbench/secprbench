#!/bin/bash
# Reproduces GH-10127: Winch derives too-small OperandSize for v128
# vector-extend loads (load8x8/16x4/32x2), so the Wasm bounds check
# under-counts the true 8-byte access width.
BIN=/work/target/x86_64-unknown-linux-gnu/release/wasmtime
IN="${INPUT:-/poc/v128_load32x2_s_oob_avx.wat}"
cp "$IN" /tmp/t.wat

$BIN explore -Ccompiler=winch -Ccranelift-has-avx=true -Omemory-reservation=0 -o /tmp/out.html /tmp/t.wat >/tmp/explore.log 2>&1
ADD_IMM=$(grep -o '"mnemonic":"add","operands":"rdx, [0-9]*"' /tmp/out.html | head -1)

$BIN run -Ccompiler=winch -Ccranelift-has-avx=true -Omemory-reservation=0 -Omemory-guard-size=0 --invoke 'v128.load32x2_s' /tmp/t.wat >/tmp/run.log 2>&1
RUN_EXIT=$?
HAS_FAULT_LINE=$(grep -c 'memory fault at wasm address' /tmp/run.log)

echo "##### RESULT SUMMARY #####"
echo "bounds-check-immediate: ${ADD_IMM:-NOT_FOUND}"
echo "run_exit: $RUN_EXIT"
echo "memory_fault_line_count: $HAS_FAULT_LINE"
if [ "$HAS_FAULT_LINE" -gt 0 ]; then
  echo "VERDICT_MARKER: BUG_PRESENT_HARDWARE_FAULT_REACHED"
  exit 1
else
  echo "VERDICT_MARKER: BOUNDS_CHECK_CAUGHT_IT_SOFTWARE_ONLY"
  exit 0
fi
