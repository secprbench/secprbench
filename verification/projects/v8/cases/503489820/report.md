# Verification report: pr_review_503489820

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: OutOfBoundsRead
- **Intro commit**: `8d161a06cdbfa8a14d261ed30d6bb465911982c3`
- **Intro parent**: `8a11afa5fd658fba7121c084275cb62de8f498dd`
- **Fix commit**: `4e101ceb0b0bd79169d2eb91949834096c8df55e`
- **Affected files**: ['src/runtime/runtime-wasm.cc']

## PoC
- source: poc-watch
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/v8/bea75cf7d1cadc5f6c1a/attempts/01/pocs/v8/503489820`
- input: `wasm-deopt-with-import.js` (1621 bytes)
- run.sh: True

## Findings

- No anomalies from deterministic checks.

## Per-version results

### pre_intro
```
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=8a11afa5fd65  note=
```
### post_intro
```
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=8d161a06cdbf  note=
  sanitizer:
    VERIFY_EXIT=134
    
    =================================================================
    ==8==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x7bf4fa5354a8 at pc 0x5579fcf02c9d bp 0x7fffcc0d5350 sp 0x7fffcc0d5348
    READ of size 8 at 0x7bf4fa5354a8 thread T0
        #0 0x5579fcf02c9c in v8::internal::wasm::NativeModule::GetCode(unsigned int) const src/wasm/wasm-code-manager.cc:1653:20
        #1 0x5579fcb5bb29 in __RT_impl_Runtime_WasmLiftoffDeoptFinish src/runtime/runtime-wasm.cc:529:55
        #2 0x5579fcb5bb29 in v8::internal::Runtime_WasmLiftoffDeoptFinish(int, unsigned long*, v8::internal::Isolate*) src/runtime/runtime-wasm.cc:498:1
        #3 0x5579fee1f708 in Builtins_WasmCEntry setup-isolate-deserialize.cc
        #4 0x7fc4faabeb2a  (<unknown module>)
        #5 0x5579fee15fd4 in Builtins_JSToWasmWrapperAsm setup-isolate-deserialize.cc
        #6 0x5579feef691c in Builtins_JSToWasmWrapper setup-isolate-deserialize.cc
```
### post_benign
```
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=8a11afa5fd65  note=
  patch_method=plain  patch_clean=True
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
