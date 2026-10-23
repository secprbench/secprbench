# Verification report: pr_review_OSSFUZZ-461519938

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: IntegerOverflow
- **Intro commit**: `b74f89caaef2174b0bfb2791ea88e44960dba11f`
- **Intro parent**: `0f0afc7fb5d30c40108d81b320823d8f5c9fbedc`
- **Fix commit**: `d41b8d95a7234cf0b34fcb84e307385fb3ef30a1`
- **Affected files**: ['libswscale/output.c']

## PoC
- source: agent-generated (initial source: incomplete)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/ffmpeg/c299d1ed9b7e1a3b7553/attempts/05/pocs/ffmpeg/OSSFUZZ-461519938`
- input: `None` (0 bytes)
- run.sh: True

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- Code inspection: the intro commit (b74f89caaef2) rewrote yuv2gbrp16_full_X_c() in libswscale/output.c so that Y gets an extra bias of -(1<<29) (`Y += (1 << 13) - (1 << 29);`, vs. the parent's `Y += 1 << 13;`) and removed the previous `av_clip_uintp2(Y + R, 30)` clamp that bounded the Y+R sum, replacing it with a direct `((Y + R) >> 14)` on the raw 32-bit sum -- exactly the change the fix commit (d41b8d95a723) targets ("Use 64bit in addition ... for RGB + Y").

Reproduction results (run_poc, identical /poc/run.sh + /poc/poc_driver.c on all three revisions):
- pre_intro (0f0afc7fb5d3): exit 0, no sanitizer report; driver prints "no overflow detected" (Y is only 8192 here, far from overflowing when summed with R=-2000000000).
- post_intro (b74f89caaef2): exit 134, UndefinedBehaviorSanitizer report at libswscale/output.c:2380 -- exactly the line/function identified by the fix ("dest16[2][i] = av_clip_uintp2(((Y + R) >> 14) ..."): "runtime error: signed integer overflow: -536862720 + -2000000000 cannot be represented in type 'int'", the same overflow class/site as OSS-Fuzz issue 461519938's "signed integer overflow: -1159988356 + -1082982400 cannot be represented in type 'int'" in yuv2gbrp16_full_X_c.
- post_benign (0f0afc7fb5d3, mechanically composed as a revert to the intro's parent -- build_version reports the identical commit hash for pre_intro and post_benign): exit 0, no sanitizer report, matching pre_intro exactly.

The same script/inputs were used unchanged across all three builds (only the extra UBSan compile flag and the relink were applied identically to each), isolating the observed regression to the intro commit's code, with the companion removing it. This directly reproduces the exact vulnerable addition and function named by the OSS-Fuzz report and the fix commit; it does not rely on an arbitrary resource threshold or an unrelated crash, and pre_intro/post_benign complete cleanly under the identical harness.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=0f0afc7fb5d3  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=bbd93d6b57aa4d5fc2d91e4ebf5df3643903311c56ae8323a3cba5b3f5b43619
  source_integrity=True
  output_tail:
    === running poc_driver against unknown ===
    poc_driver exit code: 0
    VERIFY_EXIT=0
    
    poc: calling yuv2gbrp16_full_X_c with Y-bias and R chosen so Y + R overflows a 32-bit int...
    poc: no overflow detected. rowR[0]=0 rowG[0]=0 rowB[0]=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=b74f89caaef2  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=bbd93d6b57aa4d5fc2d91e4ebf5df3643903311c56ae8323a3cba5b3f5b43619
  source_integrity=True
  sanitizer:
    === running poc_driver against unknown ===
    VERIFY_EXIT=134
    
    poc: calling yuv2gbrp16_full_X_c with Y-bias and R chosen so Y + R overflows a 32-bit int...
    libswscale/output.c:2380:43: runtime error: signed integer overflow: -536862720 + -2000000000 cannot be represented in type 'int'
        #0 0x55daa3ef3f06 in yuv2gbrp16_full_X_c /work/./libswscale/output.c:2380:43
        #1 0x55daa3f6b8da in main /poc/poc_driver.c:80:5
        #2 0x7ff25112ed8f in __libc_start_call_main csu/../sysdeps/nptl/libc_start_call_main.h:58:16
        #3 0x7ff25112ee3f in __libc_start_main csu/../csu/libc-start.c:392:3
        #4 0x55daa3dd2304 in _start (/tmp/poc_driver+0x48304) (BuildId: e0db9aca65917301e10a50758aeb404aca0870ce)
    
    SUMMARY: UndefinedBehaviorSanitizer: undefined-behavior libswscale/output.c:2380:43 in
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=0f0afc7fb5d3  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=bbd93d6b57aa4d5fc2d91e4ebf5df3643903311c56ae8323a3cba5b3f5b43619
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    === running poc_driver against unknown ===
    poc_driver exit code: 0
    VERIFY_EXIT=0
    
    poc: calling yuv2gbrp16_full_X_c with Y-bias and R chosen so Y + R overflows a 32-bit int...
    poc: no overflow detected. rowR[0]=0 rowG[0]=0 rowB[0]=0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
