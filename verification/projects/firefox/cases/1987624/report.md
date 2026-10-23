# Verification report: pr_review_1987624

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: UseAfterFree
- **Intro commit**: `75fa8115ffad385e57297cba554f546820d71208`
- **Intro parent**: `92c3bbb32a85c6ae09c92bcbefd8868a582d6aea`
- **Fix commit**: `c89c1e356e68777009764f656520e2b9079baafb`
- **Affected files**: ['js/src/wasm/WasmJS.cpp']

## PoC
- source: agent-generated (initial source: candidate_only)
- dir: `/research-data/secprbench/season100-balanced-20261001/verification-v3/cases/firefox/96d457db16e634f56c2d/attempts/01/pocs/firefox/1987624`
- input: `poc.js` (158 bytes)
- run.sh: False

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- Reproduced by running `/work/obj-verify-js/dist/bin/js /poc/poc.js` (the ASan-instrumented js shell) identically across all three built revisions. post_intro (commit 75fa8115ffad): crashes with exit 134, AddressSanitizer reports 'heap-use-after-free on address ... READ of size 4' in js::wasm::Decoder::read<unsigned int> / readFixedU32 / DecodePreamble / DecodeModuleEnvironment / Validate / WebAssembly_validate (js/src/wasm/WasmValidate.cpp, WasmJS.cpp) -- exactly the code path and bug_type (UseAfterFree) described in the report: GetBufferSource() captures a raw non-owning pointer into the ArrayBuffer before FeatureOptions::init runs arbitrary JS (the Proxy get-trap) that detaches/frees the buffer via ArrayBuffer.prototype.transfer, leaving a dangling pointer used by the decoder. pre_intro (commit 92c3bbb32a85, before the regressing refactor) and post_benign (companion fix applied on top of the same parent) both run the identical script and command to completion with exit 0 and no sanitizer report, confirming the UAF window did not exist before introduction and is closed by the benign/fix commit. No ambiguity: build succeeded cleanly for all three versions, the same PoC/input/command was used throughout, and the ASan report names the exact affected file/function from meta.json's root_cause and findings.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=92c3bbb32a85  note=build cached
  command=/work/obj-verify-js/dist/bin/js /poc/poc.js
  poc_sha256=9bad871b67bd6232f38d3a26aab8076dc6de19b2ad61b1dbc3dad92740752b99
  source_integrity=True
  output_tail:
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=75fa8115ffad  note=build cached
  command=/work/obj-verify-js/dist/bin/js /poc/poc.js
  poc_sha256=9bad871b67bd6232f38d3a26aab8076dc6de19b2ad61b1dbc3dad92740752b99
  source_integrity=True
  sanitizer:
    VERIFY_EXIT=134
    
    =================================================================
    ==8==ERROR: AddressSanitizer: heap-use-after-free on address 0x7ba001304800 at pc 0x55dd661939a7 bp 0x7fffda42fc40 sp 0x7fffda42fc38
    READ of size 4 at 0x7ba001304800 thread T0
        #0 0x55dd661939a6 in bool js::wasm::Decoder::read<unsigned int>(unsigned int*) /work/js/src/wasm/WasmBinary.h:316:5
        #1 0x55dd661939a6 in js::wasm::Decoder::readFixedU32(unsigned int*) /work/js/src/wasm/WasmBinary.h:468:57
        #2 0x55dd661939a6 in DecodePreamble(js::wasm::Decoder&) /work/js/src/wasm/WasmValidate.cpp:2472:10
        #3 0x55dd66193c33 in js::wasm::DecodeModuleEnvironment(js::wasm::Decoder&, js::wasm::CodeMetadata*, js::wasm::ModuleMetadata*) /work/js/src/wasm/WasmValidate.cpp:3939:8
        #4 0x55dd661a15a0 in js::wasm::Validate(JSContext*, js::wasm::BytecodeSource const&, js::wasm::FeatureOptions const&, mozilla::UniquePtr<char [], JS::FreePolicy>*) /work/js/src/wasm/WasmValidate.cpp:4328:8
        #5 0x55dd6603357a in WebAssembly_validate(JSContext*, unsigned int, JS::Value*) /work/js/src/wasm/WasmJS.cpp:4562:20
        #6 0x55dd63516ca2 in CallJSNative(JSContext*, bool (*)(JSContext*, unsigned int, JS::Value*), js::CallReason, JS::CallArgs const&) /work/js/src/vm/Interpreter.cpp:493:13
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=92c3bbb32a85  note=build cached
  command=/work/obj-verify-js/dist/bin/js /poc/poc.js
  poc_sha256=9bad871b67bd6232f38d3a26aab8076dc6de19b2ad61b1dbc3dad92740752b99
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    VERIFY_EXIT=0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
