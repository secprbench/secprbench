# Verification report: pr_review_2018075

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: UseAfterFree
- **Intro commit**: `398a31295dffbb51630b93f70e196e94f2728daa`
- **Intro parent**: `145adb078d7bfd8e570d086b0e9190eaf8f2f42d`
- **Fix commit**: `e055cf04d23f6a08845e2532a27bbaaa47881676`
- **Affected files**: ['js/src/vm/JSScript.cpp', 'js/src/vm/JSScript.h']

## PoC
- source: poc-watch
- dir: `/research-data/secprbench/season100-20261004-collected133-pipeline-v1/verification/cases/firefox/20d772f6768a99d535dc/attempts/01/pocs/firefox/2018075`
- input: `inline_226949d71845.js` (116 bytes)
- run.sh: False

## Findings

- No anomalies from deterministic checks.

## Per-version results

### pre_intro
```
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=145adb078d7b  note=
```
### post_intro
```
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=398a31295dff  note=
  sanitizer:
    /js +0x2e8e096]
    #41: ???[/lib/x86_64-linux-gnu/libc.so.6 +0x29d90]
    #42: __libc_start_main[/lib/x86_64-linux-gnu/libc.so.6 +0x29e40]
    #43: ???[./obj-verify-js/dist/bin/js +0x2d8fe69]
    #44: ??? (???:???)
    AddressSanitizer:DEADLYSIGNAL
    =================================================================
    ==8==ERROR: AddressSanitizer: SEGV on unknown address 0x000000000000 (pc 0x56170e35e19d bp 0x7ffc5f744930 sp 0x7ffc5f744910 T0)
    ==8==The signal is caused by a WRITE memory access.
    ==8==Hint: address points to the zero page.
        #0 0x56170e35e19d in MOZ_CrashSequence(void*, long) /work/obj-verify-js/dist/include/mozilla/Assertions.h:237:3
        #1 0x56170e35e19d in js::gc::AllocSpace<js::gc::SmallBufferRegion, 16384ul, 16ul>::isNurseryOwned(void const*) const /work/js/src/gc/BufferAllocatorInternals.h:259:5
```
### post_benign
```
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=145adb078d7b  note=
  patch_method=plain  patch_clean=True
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
