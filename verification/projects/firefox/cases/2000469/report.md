# Verification report: pr_review_2000469

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: LogicError
- **Intro commit**: `90711c04449c324bb18eb22522010fe85a051143`
- **Intro parent**: `ac5b254eb6e34c82c248ba525106c5c9d671f147`
- **Fix commit**: `2fa42593dec7de35a707f80e47898e459e4297bb`
- **Affected files**: ['js/src/jit/MIR.cpp']

## PoC
- source: agent-final (initial source: poc-watch)
- dir: `/research-data/secprbench/season100-balanced-20261001/verification-v3/cases/firefox/3641a27cadaafe3fa61b/attempts/01/pocs/firefox/2000469`
- input: `poc.js` (309 bytes)
- run.sh: False

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- The root cause is MGuardShape::foldsTo() in js/src/jit/MIR.cpp folding away a second GuardShape that is congruent-in-shape to a prior GuardShape on the same object operand, without checking the instruction's dependency() (alias-set ordering) to rule out an intervening effectful instruction that could have mutated the object's shape between the two guards. The intro commit 90711c04449c added exactly this unchecked foldsTo as part of eliminating duplicate shape guards for SetSize. The fix commit 2fa42593dec7 adds the dependency check before folding.

Verification: using the reporter's own JS reproducer (from the Bugzilla report, same PoC used across all three builds) run with the shell flags mentioned in the report (--fuzzing-safe --no-threads --fast-warmup, needed to force fast Ion warm-up so the SetSize/shape-guard folding path is JIT-compiled and exercised):
- pre_intro (ac5b254eb6e3): clean run, exit=0, no crash.
- post_intro (90711c04449c): crashes - AddressSanitizer reports SEGV inside MOZ_CrashSequence / js::NativeObject::numDynamicSlots() (JSObject-inl.h:36) called from js::NativeObject::growSlotsPure, exactly matching the bug report's "Assertion failure: slots == calculateDynamicSlots(), at vm/JSObject-inl.h:36" and its reported backtrace (growSlotsPure <- numDynamicSlots).
- post_benign (fix commit 2fa42593dec7 applied): clean run again, exit=0, no crash, same command/input.

This is a clean, deterministic repro differentiating all three builds with the identical command and input, confirming the bug was introduced by 90711c04449c and removed by the companion/fix patch.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.
- bug_marker: "re: slots == calculateDynamicSlots(), at /work/js/src/vm/JSObject-inl.h:36 ... js::NativeObject::numDynamicSlots() const ... js::NativeObject::growSlotsPure"
- pre_marker: "pre_intro: exit=0 crashed=False"
- benign_marker: "post_benign: exit=0 crashed=False"
- target execution: AddressSanitizer SEGV report in post_intro only: "MOZ_CrashSequence(void*, long) /work/obj-verify-js/dist/include/mozilla/Assertions.h:237:3 in js::NativeObject::numDynamicSlots() const /work/js/src/vm/JSObject-inl.h:36:3" called from "js::NativeObject::growSlotsPure(JSContext*, js::NativeObject*, unsigned int) /work/js/src/vm/NativeObject.cpp:437:32" — matches the Bugzilla reporter's own debug-build assertion/backtrace. pre_intro and post_benign produce exit=0 with no such report under the identical command/input.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=ac5b254eb6e3  note=build cached
  command=/work/obj-verify-js/dist/bin/js --fuzzing-safe --no-threads --fast-warmup /poc/poc.js
  poc_sha256=35e5fc1fb65ab5509aad29303d6cb57d75e154c02781cb1e11f14dc28c11c744
  source_integrity=True
  output_tail:
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=90711c04449c  note=build cached
  command=/work/obj-verify-js/dist/bin/js --fuzzing-safe --no-threads --fast-warmup /poc/poc.js
  poc_sha256=35e5fc1fb65ab5509aad29303d6cb57d75e154c02781cb1e11f14dc28c11c744
  source_integrity=True
  sanitizer:
    re: slots == calculateDynamicSlots(), at /work/js/src/vm/JSObject-inl.h:36
    #01: ???[/work/obj-verify-js/dist/bin/js +0x341d95a]
    #02: ???[/work/obj-verify-js/dist/bin/js +0x35623a7]
    #03: ??? (???:???)
    AddressSanitizer:DEADLYSIGNAL
    =================================================================
    ==8==ERROR: AddressSanitizer: SEGV on unknown address 0x000000000000 (pc 0x5615e84da986 bp 0x7ffd8ea00950 sp 0x7ffd8ea00930 T0)
    ==8==The signal is caused by a WRITE memory access.
    ==8==Hint: address points to the zero page.
        #0 0x5615e84da986 in MOZ_CrashSequence(void*, long) /work/obj-verify-js/dist/include/mozilla/Assertions.h:237:3
        #1 0x5615e84da986 in js::NativeObject::numDynamicSlots() const /work/js/src/vm/JSObject-inl.h:36:3
        #2 0x5615e861f3a6 in js::NativeObject::growSlotsPure(JSContext*, js::NativeObject*, unsigned int) /work/js/src/vm/NativeObject.cpp:437:32
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=ac5b254eb6e3  note=build cached
  command=/work/obj-verify-js/dist/bin/js --fuzzing-safe --no-threads --fast-warmup /poc/poc.js
  poc_sha256=35e5fc1fb65ab5509aad29303d6cb57d75e154c02781cb1e11f14dc28c11c744
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    VERIFY_EXIT=0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
