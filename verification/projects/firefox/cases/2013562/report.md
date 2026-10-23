# Verification report: pr_review_2013562

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: UseAfterFree
- **Intro commit**: `3b5eb00effebb2765c66f4120e770542f7c1a372`
- **Intro parent**: `85ed04eda9d264dd23a1be1cb02d6d119eb6c52a`
- **Fix commit**: `670eb2adbc70900fb1077437e452e698b0aaf488`
- **Affected files**: ['js/src/builtin/AtomicsObject.cpp']

## PoC
- source: agent-final (initial source: poc-watch)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/firefox/d7f25cfd6589bfb631a5/attempts/01/pocs/firefox/2013562`
- input: `poc.js` (1245 bytes)
- run.sh: False

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- The deterministic fast-path run (default command, no setpref) produced identical non-crashing exit=3 on all three revisions because Atomics.waitAsync is gated behind the javascript.options.atomics_wait_async pref (default false in this build) and the PoC never got past 'Atomics.waitAsync is not a function' — inconclusive, not evidence of absence. Adapting the command to add --setpref=atomics_wait_async=true (required to reach the affected code at all) reproduces the crash cleanly and reversibly: pre_intro and post_benign run the identical PoC and command to completion with exit=0; post_intro crashes deterministically under ASAN with a SEGV inside the exact function named in meta.json's root cause (atomics_notify_impl's same-thread fast path resolving a cross-realm/cross-compartment Promise without entering its realm first), via the same call stack the original reporter captured. This confirms the intro commit introduces the regression and the benign-companion/fix removes it, using one invariant reproducer across all three builds.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=85ed04eda9d2  note=build cached
  command=/work/obj-verify-js/dist/bin/js --fuzzing-safe --no-threads --setpref=atomics_wait_async=true $INPUT
  poc_sha256=f1facfd9e015b1e034e8f57ffe8852dd24bf594fce3c9c8b96d75793375bf033
  source_integrity=True
  output_tail:
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=3b5eb00effeb  note=build cached
  command=/work/obj-verify-js/dist/bin/js --fuzzing-safe --no-threads --setpref=atomics_wait_async=true $INPUT
  poc_sha256=f1facfd9e015b1e034e8f57ffe8852dd24bf594fce3c9c8b96d75793375bf033
  source_integrity=True
  sanitizer:
    st/bin/js +0x3bf0f85]
    #21: ???[/work/obj-verify-js/dist/bin/js +0x3c11b85]
    #22: ???[/work/obj-verify-js/dist/bin/js +0x2ee6461]
    #23: ???[/work/obj-verify-js/dist/bin/js +0x46ab317]
    #24: ??? (???:???)
    AddressSanitizer:DEADLYSIGNAL
    =================================================================
    ==8==ERROR: AddressSanitizer: SEGV on unknown address 0x000000000000 (pc 0x564f16e3bdfc bp 0x7fff79d199a0 sp 0x7fff79d19980 T0)
    ==8==The signal is caused by a WRITE memory access.
    ==8==Hint: address points to the zero page.
        #0 0x564f16e3bdfc in MOZ_CrashSequence(void*, long) /work/obj-verify-js/dist/include/mozilla/Assertions.h:248:3
        #1 0x564f16e3bdfc in MOZ_Crash(char const*, int, char const*) /work/obj-verify-js/dist/include/mozilla/Assertions.h:381:3
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=85ed04eda9d2  note=build cached
  command=/work/obj-verify-js/dist/bin/js --fuzzing-safe --no-threads --setpref=atomics_wait_async=true $INPUT
  poc_sha256=f1facfd9e015b1e034e8f57ffe8852dd24bf594fce3c9c8b96d75793375bf033
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    VERIFY_EXIT=0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
