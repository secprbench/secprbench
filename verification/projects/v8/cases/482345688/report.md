# Verification report: pr_review_482345688

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: DataRace
- **Intro commit**: `b9068d13bb1c33f67708cdb207a892994389941f`
- **Intro parent**: `1973b12d6241a7e7a82965447dc40fb6a8fb7bd5`
- **Fix commit**: `e194d3a40d8e676ebdeb1d1d77677d0d812c5dd9`
- **Affected files**: ['src/wasm/wasm-module.cc', 'src/wasm/wasm-module.h', 'src/wasm/wasm-code-manager.cc']

## PoC
- source: agent-generated (initial source: no_poc)
- dir: `/research-data/secprbench/season100-balanced-20261001/verification/cases/v8/1244bf4088d50a8eea8c/attempts/01/pocs/v8/482345688`
- input: `poc_debug.js` (840 bytes)
- run.sh: True

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- Root cause confirmed exactly as described in meta.json/discussion.md (public V8 fix commit e194d3a40d8e "[wasm] Fix data race on WasmModuleSignatureStorage"): intro commit b9068d13bb1c replaced the Zone-based `signature_zone` with `WasmModuleSignatureStorage signature_storage`, a mutable field written during wasm instantiation (fast-API-call signature caching) under NativeModule::allocation_mutex_, but read by WasmModule::EstimateStoredSize()/EstimateCurrentMemoryConsumption() (called from NativeModule::EstimateCurrentMemoryConsumption(), reachable via GC sampling and the %EstimateCurrentMemoryConsumption() test intrinsic) without that lock. Because the new storage class keeps its data in a std::vector<std::vector<uint8_t>> whose backing array is reallocated (and the old array freed) as it grows, the lock-free reader can dereference memory that a concurrent, lock-holding writer is in the middle of freeing -- a real, ASan-catchable heap-use-after-free, not just a benign/unobservable race. This reproduced reliably under a stress PoC designed specifically to maximize the overlap window (many imports per instantiate to force repeated reallocations; many racing writer/reader Workers; the cheap %EstimateCurrentMemoryConsumption() intrinsic for high-frequency lock-free reads). pre_intro has an analogous, textually-acknowledged-but-weaker race on the old Zone-based signature_zone (the fix commit's own message: "The same race existed before on the signature_zone_, but looks like it was less likely to trigger") -- Zone allocation is append-only/non-relocating, so it does not produce the same reallocation-induced UAF, consistent with pre_intro running clean across repeated identical-reproducer runs. post_benign restores the missing lock exactly where the root cause says it belongs (verified by diffing wasm-code-manager.cc across all three revisions) and also ran clean across repeated runs. This satisfies the invariance requirement: identical PoC/command reproduces the sanitizer report only in post_intro, and is clean in both pre_intro and post_benign.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=1973b12d6241  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=ae5be87dba4869784972875e5f55b4714276cacb1ef0280d0aab66c1de4a3461
  source_integrity=True
  output_tail:
         0
    c:V8.MemoryCodeSpaceBytesCommitted                                     262144
    c:V8.MemoryCodeSpaceBytesUsed                                           63360
    c:V8.MemoryLoSpaceBytesAvailable                                            0
    c:V8.MemoryLoSpaceBytesCommitted                                            0
    c:V8.MemoryLoSpaceBytesUsed                                                 0
    c:V8.MemoryNewSpaceBytesAvailable                                     1048512
    c:V8.MemoryNewSpaceBytesCommitted                                     2097152
    c:V8.MemoryNewSpaceBytesUsed                                                0
    c:V8.MemoryOldSpaceBytesAvailable                                      259380
    c:V8.MemoryOldSpaceBytesCommitted                                      786432
    c:V8.MemoryOldSpaceBytesUsed                                           455176
    c:V8.ObjsSinceLastFull                                                      0
    c:V8.ObjsSinceLastYoung                                                     0
    c:V8.StackInterrupts                                                      507
    VERIFY_EXIT=0
    
    V8 is running with experimental features enabled. Stability and security will suffer.
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=b9068d13bb1c  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=ae5be87dba4869784972875e5f55b4714276cacb1ef0280d0aab66c1de4a3461
  source_integrity=True
  sanitizer:
     in 136.66199999999935 ms
    VERIFY_EXIT=134
    
    V8 is running with experimental features enabled. Stability and security will suffer.
    =================================================================
    ==8==ERROR: AddressSanitizer: heap-use-after-free on address 0x7e63c9868810 at pc 0x559963b6f09a bp 0x7a51ab5ca160 sp 0x7a51ab5ca158
    READ of size 8 at 0x7e63c9868810 thread T64 (WorkerThread)
        #0 0x559963b6f099 in capacity gen/third_party/libc++/src/include/__vector/vector.h:396:41
        #1 0x559963b6f099 in TotalReservedSize src/wasm/wasm-module.h:742:33
        #2 0x559963b6f099 in v8::internal::wasm::WasmModule::EstimateStoredSize() const src/wasm/wasm-module.cc:733:28
        #3 0x559963b6f515 in v8::internal::wasm::WasmModule::EstimateCurrentMemoryConsumption() const src/wasm/wasm-module.cc:813:19
        #4 0x559963a8cb6d in v8::internal::wasm::NativeModule::EstimateCurrentMemoryConsumption() const src/wasm/wasm-code-manager.cc:2908:22
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=1973b12d6241  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=ae5be87dba4869784972875e5f55b4714276cacb1ef0280d0aab66c1de4a3461
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
         0
    c:V8.MemoryCodeSpaceBytesCommitted                                     262144
    c:V8.MemoryCodeSpaceBytesUsed                                           63360
    c:V8.MemoryLoSpaceBytesAvailable                                            0
    c:V8.MemoryLoSpaceBytesCommitted                                            0
    c:V8.MemoryLoSpaceBytesUsed                                                 0
    c:V8.MemoryNewSpaceBytesAvailable                                     1048512
    c:V8.MemoryNewSpaceBytesCommitted                                     2097152
    c:V8.MemoryNewSpaceBytesUsed                                                0
    c:V8.MemoryOldSpaceBytesAvailable                                      177200
    c:V8.MemoryOldSpaceBytesCommitted                                      786432
    c:V8.MemoryOldSpaceBytesUsed                                           454080
    c:V8.ObjsSinceLastFull                                                      0
    c:V8.ObjsSinceLastYoung                                                     0
    c:V8.StackInterrupts                                                      495
    VERIFY_EXIT=0
    
    V8 is running with experimental features enabled. Stability and security will suffer.
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
