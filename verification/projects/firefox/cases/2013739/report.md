# Verification report: pr_review_2013739

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: UseAfterFree
- **Intro commit**: `fcc2f20e35ec811fd0d3c82286a00e68ffb265be`
- **Intro parent**: `8b0694b5c8a24b1f0b8944ccefc4a5ef79503e0c`
- **Fix commit**: `05ffcde977dfaf75399cbcccf0cf966e46065a76`
- **Affected files**: ['js/src/wasm/WasmGcObject.cpp']

## PoC
- source: agent-generated (initial source: no_poc)
- dir: `/research-data/secprbench/season100-20261004-collected133-pipeline-v1/verification/cases/firefox/f3d7a65a56c2027a7200/attempts/09/pocs/firefox/2013739`
- input: `poc.js` (2077 bytes)
- run.sh: False

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- post_intro (commit fcc2f20e35ec) crashes deterministically with an AddressSanitizer SEGV inside js::gc::HeaderWord::getAtomic() reached via Cell::isForwarded -> IsForwarded<WasmArrayObject> -> MaybeForwarded<WasmArrayObject*> -> Instance::updateFrameForMovingGC -> UpdateJitActivationsForMinorGC -> Nursery minor GC path -- exactly the consumer code path discussion.md identifies as misled by the destroyed forwarding pointer (oolHeaderNew & 1 instead of | 1, always zero, misclassifying OOL data as inline so the stale wasm stack data pointer is never updated). pre_intro (parent 8b0694b5c8a2) runs the identical command to completion (exit 0, 'Done.') with no crash or sanitizer report, showing the bug is absent before the intro commit. post_benign (fix applied on top of parent) also completes cleanly (exit 0, 'Done.') with the identical command, confirming the fix removes the regression. All three builds used the same PoC bytes and same invocation, satisfying the invariance requirement. This is a genuine use-after-free: the wasm frame retains a stale pointer into freed/relocated nursery memory after the OOL array data block is promoted/moved during a minor GC, and subsequent array accesses through that pointer read from the freed region (observed here as SIGSEGV reading unmapped/clobbered memory, consistent with ASan poisoning catching the invalid access).

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=8b0694b5c8a2  note=build cached
  command=/work/obj-verify-js/dist/bin/js --wasm-compiler=optimizing /poc/poc.js
  poc_sha256=e967ee059f1b0e1a8eeaaf90412b2e1b327ecd8948ca29f3255fc0452b267496
  source_integrity=True
  output_tail:
    Phase 1: warmup for Ion tier-up...
    Phase 2: GC pressure after Ion tier-up...
    Done.
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=fcc2f20e35ec  note=build cached
  command=/work/obj-verify-js/dist/bin/js --wasm-compiler=optimizing /poc/poc.js
  poc_sha256=e967ee059f1b0e1a8eeaaf90412b2e1b327ecd8948ca29f3255fc0452b267496
  source_integrity=True
  sanitizer:
    Phase 1: warmup for Ion tier-up...
    VERIFY_EXIT=134
    
    AddressSanitizer:DEADLYSIGNAL
    =================================================================
    ==8==ERROR: AddressSanitizer: SEGV on unknown address 0x000485a525a5 (pc 0x5568100d803f bp 0x7ffca043cbf0 sp 0x7ffca043cb70 T0)
    ==8==The signal is caused by a READ memory access.
        #0 0x5568100d803f in js::gc::HeaderWord::getAtomic() const /work/js/src/gc/Cell.h:101:12
        #1 0x5568100d803f in js::gc::HeaderWord::flags() const /work/js/src/gc/Cell.h:117:36
        #2 0x5568100d803f in js::gc::HeaderWord::isForwarded() const /work/js/src/gc/Cell.h:118:37
        #3 0x5568100d803f in js::gc::Cell::isForwarded() const /work/js/src/gc/Cell.h:154:45
        #4 0x5568100d803f in bool js::gc::IsForwarded<js::WasmArrayObject>(js::WasmArrayObject const*) /work/js/src/gc/Marking-inl.h:97:13
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=8b0694b5c8a2  note=build cached
  command=/work/obj-verify-js/dist/bin/js --wasm-compiler=optimizing /poc/poc.js
  poc_sha256=e967ee059f1b0e1a8eeaaf90412b2e1b327ecd8948ca29f3255fc0452b267496
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    Phase 1: warmup for Ion tier-up...
    Phase 2: GC pressure after Ion tier-up...
    Done.
    VERIFY_EXIT=0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
