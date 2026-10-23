# Verification report: pr_review_GH-10127

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: LogicError
- **Intro commit**: `bb5e4bbaf9a60b07213ccdd1973bc0606c22c822`
- **Intro parent**: `f099784806591a4ff6caf570c25c71f946fe2934`
- **Fix commit**: `db7fb47b8e1414c43d0ebe3b619a547fd7a0bcf9`
- **Affected files**: ['winch/codegen/src/masm.rs', 'winch/codegen/src/isa/x64/masm.rs']

## PoC
- source: agent-final (initial source: poc-watch)
- dir: `/research-data/secprbench/season100-balanced-20261001/verification-v2/cases/wasmtime/b1cdf125cb7b8fa3f900/attempts/01/pocs/wasmtime/GH-10127`
- input: `v128_load32x2_s_oob_avx.wat` (1084 bytes)
- run.sh: True

## Findings

- Exact bug and unaffected output lines matched the shared three-version Docker replay.
- Root cause per meta.json: the Jan-2025 Winch refactor (#10012, landed as intro commit bb5e4bbaf9a6) conflated "bits per source lane before widening" with "total bytes read from memory" in LoadKind::derive_operand_size() for VectorExtend SIMD loads (v128.load8x8/16x4/32x2 _s/_u). That undersized OperandSize is reused both to emit the actual load instruction and to size the Wasm linear-memory bounds check, so the bounds check under-counts the true 8-byte access width.

I verified this by building pre_intro, post_intro and post_benign and running the exact same /poc/run.sh (same input file, same flags) via run_poc on each. The script runs each revision's actual Winch backend (via `wasmtime explore -Ccompiler=winch ...`) to read off the compiled bounds-check immediate, and separately executes the module live (via `wasmtime run -Ccompiler=winch ... -Omemory-guard-size=0 --invoke ...`) to see whether the undersized check actually lets an out-of-bounds 8-byte read reach a real unmapped page.

Results: pre_intro and post_benign both compile the access with the correct `add rdx, 8` and never reach the real OOB read (bounds check traps it first, memory_fault_line_count=0). post_intro compiles the access with the buggy `add rdx, 4`, which lets the check pass; the subsequent real 8-byte vector load then runs 1 byte past the end of the mapped 1-page memory and triggers a genuine hardware SIGSEGV, visible as Wasmtime's extra "memory fault at wasm address 0x10000 ..." diagnostic (memory_fault_line_count=1) -- something that does not occur in pre_intro or post_benign. This is an exact, mechanism-level match to the described root cause (wrong per-lane vs total-access-width size used for bounds checking) and cleanly distinguishes "introduces the bug" (post_intro only) from "fixes it" (post_benign, identical to pre_intro). The deterministic fast-path's default PoC run showed no difference on any revision because the default run command used neither the Winch backend (Cranelift is the CLI default) nor disabled guard pages, so it never reached the code path this task implicates.

## Agent oracle

- machine gate: verified (behavioral)
- basis: Exact bug and unaffected output lines matched the shared three-version Docker replay.
- bug_marker: "VERDICT_MARKER: BUG_PRESENT_HARDWARE_FAULT_REACHED"
- pre_marker: "VERDICT_MARKER: BOUNDS_CHECK_CAUGHT_IT_SOFTWARE_ONLY"
- benign_marker: "VERDICT_MARKER: BOUNDS_CHECK_CAUGHT_IT_SOFTWARE_ONLY"
- target execution: run_poc(run.sh) results, identical command/input across revisions:
- pre_intro (f09978480659): bounds-check-immediate = "add rdx, 8"; memory_fault_line_count = 0; VERDICT_MARKER=BOUNDS_CHECK_CAUGHT_IT_SOFTWARE_ONLY; script exit 0.
- post_intro (bb5e4bbaf9a6): bounds-check-immediate = "add rdx, 4"; memory_fault_line_count = 1; VERDICT_MARKER=BUG_PRESENT_HARDWARE_FAULT_REACHED; script exit 1.
- post_benign (mechanical revert, = intro_parent f09978480659): bounds-check-immediate = "add rdx, 8"; memory_fault_line_count = 0; VERDICT_MARKER=BOUNDS_CHECK_CAUGHT_IT_SOFTWARE_ONLY; script exit 0.
Only post_intro shows the undersized 4-byte bounds-check width and the resulting real hardware OOB fault; pre_intro and post_benign are identical to each other and both match the correct/fixed 8-byte width.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=f09978480659  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=6c5b0c8ddd5a39cc21f515096e8eef405ad6179de604237ed2c3827d30386382
  source_integrity=True
  output_tail:
    ##### RESULT SUMMARY #####
    bounds-check-immediate: "mnemonic":"add","operands":"rdx, 8"
    run_exit: 134
    memory_fault_line_count: 0
    VERDICT_MARKER: BOUNDS_CHECK_CAUGHT_IT_SOFTWARE_ONLY
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=1  poc_ran=True  patched=False
  commit=bb5e4bbaf9a6  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=6c5b0c8ddd5a39cc21f515096e8eef405ad6179de604237ed2c3827d30386382
  source_integrity=True
  output_tail:
    ##### RESULT SUMMARY #####
    bounds-check-immediate: "mnemonic":"add","operands":"rdx, 4"
    run_exit: 134
    memory_fault_line_count: 1
    VERDICT_MARKER: BUG_PRESENT_HARDWARE_FAULT_REACHED
    VERIFY_EXIT=1
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=f09978480659  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=6c5b0c8ddd5a39cc21f515096e8eef405ad6179de604237ed2c3827d30386382
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    ##### RESULT SUMMARY #####
    bounds-check-immediate: "mnemonic":"add","operands":"rdx, 8"
    run_exit: 134
    memory_fault_line_count: 0
    VERDICT_MARKER: BOUNDS_CHECK_CAUGHT_IT_SOFTWARE_ONLY
    VERIFY_EXIT=0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
