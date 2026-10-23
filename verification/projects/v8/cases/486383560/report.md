# Verification report: pr_review_486383560

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: UseAfterFree
- **Intro commit**: `b2123b6a6014b2a961192815be50f8b071845250`
- **Intro parent**: `ff2b5a672985c0d18d2871732dd4407fd107032d`
- **Fix commit**: `d747340f097ee16ddadb5cdf05c410fcfa8ef2b1`
- **Affected files**: ['src/d8/d8.cc']

## PoC
- source: poc-watch
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/v8/4201dbdccf0f062ba18f/attempts/01/pocs/v8/486383560`
- input: `regress-486383560.js` (256 bytes)
- run.sh: True

## Findings

- No anomalies from deterministic checks.

## Per-version results

### pre_intro
```
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=ff2b5a672985  note=
```
### post_intro
```
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=b2123b6a6014  note=
  sanitizer:
    VERIFY_EXIT=134
    
    =================================================================
    ==8==ERROR: AddressSanitizer: heap-use-after-free on address 0x62500002320a at pc 0x55c47ff72d50 bp 0x7ffe76139520 sp 0x7ffe76139518
    READ of size 1 at 0x62500002320a thread T0
        #0 0x55c47ff72d4f in index src/handles/global-handles.cc:340:34
        #1 0x55c47ff72d4f in From src/handles/global-handles.cc:114:38
        #2 0x55c47ff72d4f in v8::internal::GlobalHandles::NodeSpace<v8::internal::GlobalHandles::Node>::Release(v8::internal::GlobalHandles::Node*) src/handles/global-handles.cc:270:22
        #3 0x55c47f97f7b4 in Reset include/v8-persistent-handle.h:475:3
        #4 0x55c47f97f7b4 in ~Global include/v8-persistent-handle.h:404:31
        #5 0x55c47f97f7b4 in ~pair buildtools/third_party/libc++/trunk/include/__utility/pair.h:46:29
        #6 0x55c47f97f7b4 in ~pair buildtools/third_party/libc++/trunk/include/__utility/pair.h:46:29
```
### post_benign
```
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=ff2b5a672985  note=
  patch_method=plain  patch_clean=True
```

## Interpretation

The intro commit introduces the bug (clean before, crash after) and, where a benign companion exists, the benign patch removes it. Labels are consistent with execution.
