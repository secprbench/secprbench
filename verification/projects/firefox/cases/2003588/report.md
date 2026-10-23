# Verification report: pr_review_2003588

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: UseAfterFree
- **Intro commit**: `9bd0056bb97aef3f6f44ec457417821f92a7eb4c`
- **Intro parent**: `9108500bb368dae51d67883f32c85dcbdc8406ba`
- **Fix commit**: `0264cf850afd91cdd3956066e0b00b982566f684`
- **Affected files**: ['js/src/proxy/CrossCompartmentWrapper.cpp', 'js/src/debugger/Debugger.cpp']

## PoC
- source: agent-final (initial source: poc-watch)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/firefox/7c55e436979e2f504fe1/attempts/01/pocs/firefox/2003588`
- input: `poc.js` (323 bytes)
- run.sh: False

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- pre_intro (parent 9108500bb368): exit=0, clean. Output: "CAUGHT: TypeError: can't access dead object" then "DONE" — the CCW was properly nuked by nukeAllCCWs() and the subsequent access throws a well-formed, catchable JS exception; no crash, no sanitizer report. post_intro (9bd0056bb97a, the labelled intro commit): exit=134, crashed. AddressSanitizer reports a SEGV (write to address 0) with stack MOZ_CrashSequence -> JS::Compartment::wrap (vm/Compartment-inl.h:105) -> js::CrossCompartmentWrapper::get (proxy/CrossCompartmentWrapper.cpp:184) -> Proxy::getInternal/get -> GetProperty -> with_GetProperty -> DebugEnvironmentProxyHandler::getMaybeSentinelValue -> ... This exactly matches the reporter's own gdb backtrace in the Bugzilla report (same functions and same source lines: Compartment-inl.h:105, CrossCompartmentWrapper.cpp:184, EnvironmentObject.cpp with_GetProperty). The crash happens natively inside the engine before any JS-level try/catch can intervene, confirming the regression: commit 9bd0056bb97a special-cased NukeCrossCompartmentWrappers() to skip nuking CCWs that point at the Debugger object, but did not give js::AllowNewWrapper() the same exception, so Compartment::wrap()'s invariant (that an existing live wrapper and the "already nuked" gate agree) is violated, producing corrupted/incoherent wrapper state and a use-after-free-style crash (null-pointer dereference inside the release-assert path) when the proxy get path runs. post_benign (fix 0264cf850afd, mechanically composed companion): exit=0, clean. Output: "NO_EXCEPTION" then "DONE" — getVariable("x") now succeeds without throwing and without crashing, i.e., AllowNewWrapper() was updated to match the nuke exception, restoring Compartment::wrap()'s invariant. The same reproducer (poc.js, same command) yields: clean pre_intro -> sanitizer-crash post_intro (matching the reported bug's exact backtrace) -> clean post_benign, confirming both introduction and the benign fix as labelled.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=9108500bb368  note=build cached
  command=./obj-verify-js/dist/bin/js "$INPUT"
  poc_sha256=6b2b0dc756d92b18532fd62f8fb03333e6502e6250f7887a1401f9830844c449
  source_integrity=True
  output_tail:
    CAUGHT: TypeError: can't access dead object
    DONE
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=9bd0056bb97a  note=build cached
  command=./obj-verify-js/dist/bin/js "$INPUT"
  poc_sha256=6b2b0dc756d92b18532fd62f8fb03333e6502e6250f7887a1401f9830844c449
  source_integrity=True
  sanitizer:
    /js +0x2d8c85e]
    #39: ???[/lib/x86_64-linux-gnu/libc.so.6 +0x29d90]
    #40: __libc_start_main[/lib/x86_64-linux-gnu/libc.so.6 +0x29e40]
    #41: ???[./obj-verify-js/dist/bin/js +0x2c8e399]
    #42: ??? (???:???)
    AddressSanitizer:DEADLYSIGNAL
    =================================================================
    ==8==ERROR: AddressSanitizer: SEGV on unknown address 0x000000000000 (pc 0x55c5a99c0cf0 bp 0x7ffc3aacab30 sp 0x7ffc3aaca920 T0)
    ==8==The signal is caused by a WRITE memory access.
    ==8==Hint: address points to the zero page.
        #0 0x55c5a99c0cf0 in MOZ_CrashSequence(void*, long) /work/obj-verify-js/dist/include/mozilla/Assertions.h:237:3
        #1 0x55c5a99c0cf0 in JS::Compartment::wrap(JSContext*, JS::MutableHandle<JS::Value>) /work/js/src/vm/Compartment-inl.h:105:3
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=9108500bb368  note=build cached
  command=./obj-verify-js/dist/bin/js "$INPUT"
  poc_sha256=6b2b0dc756d92b18532fd62f8fb03333e6502e6250f7887a1401f9830844c449
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    NO_EXCEPTION
    DONE
    VERIFY_EXIT=0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
