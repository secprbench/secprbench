# Verification report: pr_review_1987290

- **Status**: `inconclusive`
- **Intro verified**: None
- **Benign verified**: None
- **Bug type**: OutOfBoundsRead
- **Intro commit**: `321172222a2ea5ef15aa7ea8ff4fc27be3064c94`
- **Intro parent**: `cd57ef3c4dbd0cb0bb12a893291911f1767e3680`
- **Fix commit**: `2b8155c2c4c299955d4ae81423992ed56a838aee`
- **Affected files**: ['js/src/builtin/FinalizationRegistryObject.cpp']

## PoC
- source: agent-final (initial source: poc-watch)
- dir: `/research-data/secprbench/season100-balanced-20261001/verification-v3/cases/firefox/de45666918eaf16abcc4/attempts/01/pocs/firefox/1987290`
- input: `poc.js` (64 bytes)
- run.sh: False

## Findings

- The agent claim lacks a matching admissible three-version oracle.
- Root cause per meta.json: Bug 1863140 Part 3 (commit 321172222a2e) rewrote FinalizationRegistryObject::unregister to support non-object unregister tokens, replacing the old safe pattern (`args.get(0).isObject()` then `&args[0].toObject()`, only indexing after confirming argc covers index 0) with an unconditional `RootedValue unregisterToken(cx, args[0])` constructed before any argc validation. Calling `unregister()` with zero arguments therefore makes CallArgsBase::operator[] index into the native call-arguments array one past argc (an out-of-bounds read of that array), which js/src/js/CallArgs.h guards with a release assert (MOZ_RELEASE_ASSERT(i < argc_)) rather than letting undefined memory be read silently; firing that guard aborts the process, which AddressSanitizer intercepts and reports as 'SEGV on unknown address 0x0' (the crash-reporting sequence itself writes to the null guard address, hence 'WRITE memory access' in the ASAN summary — this is the crash mechanism, not the underlying bug class). This exactly reproduces the reporter's Windows crash ('Assertion failure: i < argc_, at .../js/CallArgs.h:213', frame js::FinalizationRegistryObject::unregister at FinalizationRegistryObject.cpp:592). I ran the identical poc.js with the default run command against all three built revisions: pre_intro (parent cd57ef3c4dbd) throws a clean, handled TypeError ('Invalid unregister token passed to FinalizationRegistry.unregister'), exit 3, no sanitizer involvement — the pre-regression args.get(0) validation path. post_intro (321172222a2e) crashes every time (reran twice to confirm determinism) with the ASAN SEGV/assert report pinned to the exact regressed line. post_benign (fix 2b8155c2c4c2, which changes `args[0]` back to `args.get(0)` per the 'Part 1' commit message) again exits 3 with the same handled TypeError and no crash, confirming the companion patch removes the bug. All three builds succeeded and used the same PoC/command, satisfying the invariant-reproducer requirement. Because this specific out-of-bounds index is intercepted by a release assert rather than manifesting as a classic ASAN heap/stack-buffer-overflow 'READ of size N' report, I use bug_class=other for this record (the automated memory-safety evidence gate requires that literal ASAN buffer-overflow signature), but the reproduction itself is an unambiguous, deterministic match for the labelled OutOfBoundsRead regression: introduced at 321172222a2e and fixed at 2b8155c2c4c2.

## Agent oracle

- machine gate: inconclusive (unproven)
- basis: The agent claim lacks a matching admissible three-version oracle.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=3  poc_ran=True  patched=False
  commit=cd57ef3c4dbd  note=build cached
  command=./obj-verify-js/dist/bin/js "$INPUT"
  poc_sha256=be3056577c18c5f82d22e195bbd40fb185c109203782e4a54b720de120e9bd6a
  source_integrity=True
  output_tail:
    VERIFY_EXIT=3
    
    /poc/poc.js:2:3 TypeError: Invalid unregister token passed to FinalizationRegistry.unregister
    Stack:
      @/poc/poc.js:2:3
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=321172222a2e  note=build cached
  command=./obj-verify-js/dist/bin/js "$INPUT"
  poc_sha256=be3056577c18c5f82d22e195bbd40fb185c109203782e4a54b720de120e9bd6a
  source_integrity=True
  sanitizer:
    /js +0x2d3b0ce]
    #14: ???[/lib/x86_64-linux-gnu/libc.so.6 +0x29d90]
    #15: __libc_start_main[/lib/x86_64-linux-gnu/libc.so.6 +0x29e40]
    #16: ???[./obj-verify-js/dist/bin/js +0x2c3d109]
    #17: ??? (???:???)
    AddressSanitizer:DEADLYSIGNAL
    =================================================================
    ==8==ERROR: AddressSanitizer: SEGV on unknown address 0x000000000000 (pc 0x5633194185c2 bp 0x7ffd9d2ca330 sp 0x7ffd9d2ca1c0 T0)
    ==8==The signal is caused by a WRITE memory access.
    ==8==Hint: address points to the zero page.
        #0 0x5633194185c2 in MOZ_CrashSequence(void*, long) /work/obj-verify-js/dist/include/mozilla/Assertions.h:248:3
        #1 0x5633194185c2 in JS::detail::CallArgsBase<JS::detail::IncludeUsedRval>::operator[](unsigned int) const /work/obj-verify-js/dist/include/js/CallArgs.h:213:5
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=3  poc_ran=True  patched=True
  commit=cd57ef3c4dbd  note=build cached
  command=./obj-verify-js/dist/bin/js "$INPUT"
  poc_sha256=be3056577c18c5f82d22e195bbd40fb185c109203782e4a54b720de120e9bd6a
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    VERIFY_EXIT=3
    
    /poc/poc.js:2:3 TypeError: Invalid unregister token passed to FinalizationRegistry.unregister
    Stack:
      @/poc/poc.js:2:3
```

## Interpretation

The available evidence does not establish both labels. Inspect the findings and per-version results for the limiting reason.
