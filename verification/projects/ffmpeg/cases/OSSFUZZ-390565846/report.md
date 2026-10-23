# Verification report: pr_review_OSSFUZZ-390565846

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: NullPointerDereference
- **Intro commit**: `8eb1d76e146a0e557d596a4039efebac746b4d83`
- **Intro parent**: `d5873be583ada9e1fb887e2fe8dcfd4b12e0efcd`
- **Fix commit**: `a50d36b5fd3914795f470abefcd37699b23bc8d4`
- **Affected files**: ['libavcodec/vvc/refs.c']

## PoC
- source: agent-generated (initial source: incomplete)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/ffmpeg/8b2da4c140f71c6a196a/attempts/01/pocs/ffmpeg/OSSFUZZ-390565846`
- input: `None` (0 bytes)
- run.sh: True

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- Root cause matches meta.json exactly: set_pict_type() in libavcodec/vvc/refs.c, introduced by commit 8eb1d76e146a, iterates over all CBS units of the current access unit and, for every unit with type <= VVC_RSV_IRAP_11, unconditionally dereferences unit->content_ref as an H266RawSliceHeader* (`const H266RawSliceHeader *rsh = unit->content_ref; has_inter |= !IS_I(rsh);`) without checking it for NULL. A CBS unit with a reserved VCL NAL type (e.g. VVC_RSV_VCL_4) is exactly such a unit whose content_ref is never populated (decompose fails with the tolerated ENOSYS), so this is a real, reachable NULL-pointer dereference, not a mislabeled bug. run_poc results: (1) pre_intro (parent d5873be583ad) — refs.c has no set_pict_type function at all (grep found zero matches); the harness decode fails cleanly with a normal libavcodec error code (AVERROR_INVALIDDATA from the unrelated reserved-type NAL not being handled by decode_nal_unit) and the process exits normally (exit=0, crashed=False), no sanitizer report. (2) post_intro (8eb1d76e146a) — run_poc reports crashed=True with an AddressSanitizer 'SEGV on unknown address 0x000000000541 ... READ memory access' and a clean crash stack: set_pict_type (refs.c:189:31) <- ff_vvc_set_new_ref (refs.c:223) <- frame_start (dec.c:712) <- slice_start <- decode_slice <- decode_nal_unit <- decode_nal_units <- vvc_decode_frame <- avcodec_send_packet <- main. Line 189 is exactly `has_inter |= !IS_I(rsh);`, the dereference identified in meta.json's root_cause. (3) post_benign — libavcodec/vvc/refs.c was inspected directly and confirmed to contain the fix: `if (unit->content_ref && unit->type <= VVC_RSV_IRAP_11) { ... }`; run_poc on the identical PoC against post_benign completes cleanly (exit=0, crashed=False), same benign path as pre_intro, no sanitizer report. This cleanly establishes: bug absent pre_intro (code path didn't exist), present and crashing at post_intro under the exact same reproducer, and fixed at post_benign under the exact same reproducer.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=d5873be583ad  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=ae6647403b540a6dd0977da5f36187dfd495a99e3b3aa64984a580f644a77d10
  source_integrity=True
  output_tail:
    VERIFY_EXIT=0
    
    Built 50-byte VVC packet
    [vvc @ 0x618000000480] frame     0, P(  0,   0) failed with -1094995529
    send_packet -> 0
    receive_frame -> -11
    DONE (no crash)
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=1  poc_ran=True  patched=False
  commit=8eb1d76e146a  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=ae6647403b540a6dd0977da5f36187dfd495a99e3b3aa64984a580f644a77d10
  source_integrity=True
  sanitizer:
    VERIFY_EXIT=1
    
    Built 50-byte VVC packet
    AddressSanitizer:DEADLYSIGNAL
    =================================================================
    ==8==ERROR: AddressSanitizer: SEGV on unknown address 0x000000000541 (pc 0x560382a7ed80 bp 0x7ffd189644d0 sp 0x7ffd18964460 T0)
    ==8==The signal is caused by a READ memory access.
    ==8==Hint: address points to the zero page.
        #0 0x560382a7ed80 in set_pict_type /work/libavcodec/vvc/refs.c:189:31
        #1 0x560382a7ed80 in ff_vvc_set_new_ref /work/libavcodec/vvc/refs.c:223:5
        #2 0x5603829f9565 in frame_start /work/libavcodec/vvc/dec.c:712:16
        #3 0x5603829f9565 in slice_start /work/libavcodec/vvc/dec.c:749:15
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=d5873be583ad  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=ae6647403b540a6dd0977da5f36187dfd495a99e3b3aa64984a580f644a77d10
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    VERIFY_EXIT=0
    
    Built 50-byte VVC packet
    [vvc @ 0x618000000480] frame     0, P(  0,   0) failed with -1094995529
    send_packet -> 0
    receive_frame -> -11
    DONE (no crash)
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
