# Verification report: pr_review_2003589

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: LogicError
- **Intro commit**: `7c0e78c0e4575dda295abed143b32888ac5a8f5d`
- **Intro parent**: `7ef21c323fbce385ee230dc6be03658081af012d`
- **Fix commit**: `1d09788fc8234e4ab0dc3b9f2a99ff66cb90e274`
- **Affected files**: ['js/src/jit/IonAnalysis.cpp', 'js/src/vm/Iteration.cpp', 'js/src/jit/CodeGenerator.cpp']

## PoC
- source: agent-final (initial source: poc-watch)
- dir: `/research-data/secprbench/season100-20261002-repairs/firefox-2003589-true-intro-import-v1/verification-unified28-v1/cases/firefox/8afbf1bbe18e6cc7aa88/attempts/01/pocs/firefox/2003589`
- input: `poc.js` (108 bytes)
- run.sh: False

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- meta.json: intro=7c0e78c0e457 ('Integrate with existing iterator indices optimizations'), parent/pre=7ef21c323fbc, fix/benign-companion=1d09788fc823 ('Only enumerate own properties in Object.keys ObjToIterator'). Root cause per findings: the new LoadIteratorElement/iterator-indices fast path lets Object.keys reuse an iterator built via a path that can still enumerate prototype properties (including through a Proxy trap that runs arbitrary script), which the new optimization did not expect, leading to script execution where none should be allowed (hits the disallowArbitraryCode() assertion / crashes in debug-equivalent ASan build, matching the reported sec-high JIT bug and its committed regression test object-keys-proxy-proto.js).

Verification: used the exact reporter PoC (also matches the committed jit-test regression file byte-for-byte) on all three builds with the same command `js --fuzzing-safe --no-threads --ion-eager poc.js`:
- pre_intro (7ef21c323fbc): exit=0, no crash.
- post_intro (7c0e78c0e457): exit=134 (SIGABRT via ASan), crash report is an AddressSanitizer SEGV inside MOZ_CrashSequence / js::RunScript (Interpreter.cpp:406-407), reached through js::Call -> ScriptedProxyHandler::getOwnPropertyDescriptor -> BaseProxyHandler::getOwnEnumerablePropertyKeys -> Proxy::getOwnEnumerablePropertyKeys -> PropertyEnumerator::enumerateProxyProperties -> PropertyEnumerator::snapshot -> GetIteratorImpl -> GetIteratorUnregistered, i.e. exactly the Object.keys iterator/enumeration path named in the root cause and the reported assertion-failure stack.
- post_benign (companion patch on top of intro, built from commit 7ef21c323fbc tag but containing the fix): exit=0, no crash, matching pre_intro.

The deterministic fast-path runner used the plain default run command which does not pass the JIT flags (--fuzzing-safe --no-threads --ion-eager) needed to force Ion-eager compilation and hit the optimization; with those flags (taken directly from the reporter's command line in discussion.md) the crash is 100% reproducible on post_intro only. This cleanly satisfies: crash present only in post_intro, absent in both pre_intro and post_benign, under the identical reproducer command/input across all three builds.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=7ef21c323fbc  note=build cached
  command=/work/obj-verify-js/dist/bin/js --fuzzing-safe --no-threads --ion-eager $INPUT
  poc_sha256=652aaf53452c537f47db1be866d64af979dd80a84788656827b0a17ad0e297d1
  source_integrity=True
  output_tail:
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=7c0e78c0e457  note=build cached
  command=/work/obj-verify-js/dist/bin/js --fuzzing-safe --no-threads --ion-eager $INPUT
  poc_sha256=652aaf53452c537f47db1be866d64af979dd80a84788656827b0a17ad0e297d1
  source_integrity=True
  sanitizer:
    st/bin/js +0x3ced955]
    #08: ???[/work/obj-verify-js/dist/bin/js +0x336f855]
    #09: ???[/work/obj-verify-js/dist/bin/js +0x3320426]
    #10: ???[/work/obj-verify-js/dist/bin/js +0x3325a1c]
    #11: ??? (???:???)
    AddressSanitizer:DEADLYSIGNAL
    =================================================================
    ==8==ERROR: AddressSanitizer: SEGV on unknown address 0x000000000000 (pc 0x55eff888e18d bp 0x7ffe3f97b7d0 sp 0x7ffe3f97b6c0 T0)
    ==8==The signal is caused by a WRITE memory access.
    ==8==Hint: address points to the zero page.
        #0 0x55eff888e18d in MOZ_CrashSequence(void*, long) /work/obj-verify-js/dist/include/mozilla/Assertions.h:237:3
        #1 0x55eff888e18d in js::RunScript(JSContext*, js::RunState&) /work/js/src/vm/Interpreter.cpp:406:3
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=7ef21c323fbc  note=build cached
  command=/work/obj-verify-js/dist/bin/js --fuzzing-safe --no-threads --ion-eager $INPUT
  poc_sha256=652aaf53452c537f47db1be866d64af979dd80a84788656827b0a17ad0e297d1
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    VERIFY_EXIT=0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
