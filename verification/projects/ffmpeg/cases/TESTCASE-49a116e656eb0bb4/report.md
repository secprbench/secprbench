# Verification report: pr_review_TESTCASE-49a116e656eb0bb4

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: BufferOverflow
- **Intro commit**: `baad75cafa6bac298b72c177f657a2eb8e31cff1`
- **Intro parent**: `86977fdb6bb0ba553a9c654309eb9c028a3777b4`
- **Fix commit**: `2e32276872d330b9a9e97de68d62dd7a679b1221`
- **Affected files**: ['libavcodec/aac/aacdec_usac_mps212.c']

## PoC
- source: agent-generated (initial source: no_poc)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/ffmpeg/f2ad7d64afbcaf463806/attempts/04/pocs/ffmpeg/TESTCASE-49a116e656eb0bb4`
- input: `None` (0 bytes)
- run.sh: True

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- Verified via run_poc with the identical /poc/run.sh + /poc/poc.c against all three built revisions, all runs completing (no build/usage errors).

post_intro (baad75cafa6b): exit=134, crashed=True. AddressSanitizer reports a stack-buffer-overflow: 'READ of size 2 ... #0 attach_lsb aacdec_usac_mps212.c:368:19 #1 ec_pair_dec aacdec_usac_mps212.c:533:9 #2 ff_aac_ec_data_dec aacdec_usac_mps212.c:646:19'. The frame dump shows the access at offset 448 overflowing the 112-byte 'data_pair.i' stack object (int16_t data_pair[2][28], declared at aacdec_usac_mps212.c:426 — exactly the array named in meta.json's root_cause) — caused by attach_lsb() iterating the full nb_bands=28 count starting from the pointer huff_decode() had advanced by one element via its undocumented 'data[0] += 1; data[1] += 1;' mutation.

pre_intro (86977fdb6bb0, direct parent of the intro commit): exit=0, crashed=False. The harness's __has_include check correctly detects that libavcodec/aac/aacdec_usac_mps212.h does not exist in this revision (confirmed independently via find/grep across /work: no aacdec_usac_mps212.* files, no ff_aac_ec_data_dec symbol anywhere) and cleanly prints 'MPS212 decoder not present in this revision; nothing to test', exiting 0. This is a clean, non-crashing completion: the entire USAC MPS-212 lossless-data decoder (and the vulnerable ec_pair_dec/attach_lsb/huff_decode logic) was introduced wholesale by the intro commit, so pre_intro structurally cannot exhibit this defect — there is no prior code path to regress from.

post_benign (fix applied on top of the intro commit): exit=0, crashed=False. The header/symbol exist and match, so the harness runs the real test with the byte-for-byte identical crafted input and completes normally: 'ff_aac_ec_data_dec returned 0', no sanitizer report. Source inspection of this revision confirms the fix: the two attach_lsb() calls in ec_pair_dec() now use the unshifted base arrays 'data_pair[0]'/'data_pair[1]' instead of the possibly-advanced p_data[0]/p_data[1] pointers, removing the pointer/iteration-count mismatch.

Together: post_intro crashes with an unambiguous, target-specific AddressSanitizer stack-buffer-overflow at the exact call site named in the root cause; pre_intro completes cleanly because the vulnerable code was not yet introduced; post_benign completes cleanly with the same input because the fix removes the pointer/loop-bound mismatch. intro_verified=yes, benign_verified=yes.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=86977fdb6bb0  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=ab01e4f61c6cf108d709cc2140f2721e58331766c3c0c31f5cdd25d1bd4bf0ae
  source_integrity=True
  output_tail:
    MPS212 decoder not present in this revision; nothing to test
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=baad75cafa6b  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=ab01e4f61c6cf108d709cc2140f2721e58331766c3c0c31f5cdd25d1bd4bf0ae
  source_integrity=True
  sanitizer:
    VERIFY_EXIT=134
    
    =================================================================
    ==8==ERROR: AddressSanitizer: stack-buffer-overflow on address 0x7ffee7a8d580 at pc 0x557633c70f02 bp 0x7ffee7a8d3b0 sp 0x7ffee7a8d3a8
    READ of size 2 at 0x7ffee7a8d580 thread T0
        #0 0x557633c70f01 in attach_lsb /work/libavcodec/aac/aacdec_usac_mps212.c:368:19
        #1 0x557633c70f01 in ec_pair_dec /work/libavcodec/aac/aacdec_usac_mps212.c:533:9
        #2 0x557633c70f01 in ff_aac_ec_data_dec /work/libavcodec/aac/aacdec_usac_mps212.c:646:19
        #3 0x557633c6db46 in main /poc/poc.c:66:15
        #4 0x7f2500b31d8f in __libc_start_call_main csu/../sysdeps/nptl/libc_start_call_main.h:58:16
        #5 0x7f2500b31e3f in __libc_start_main csu/../csu/libc-start.c:392:3
        #6 0x557633bafc84 in _start (/tmp/poc_run+0x28c84) (BuildId: 4c9a80cfd328238d977341d7f05f232f795fbe60)
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=86977fdb6bb0  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=ab01e4f61c6cf108d709cc2140f2721e58331766c3c0c31f5cdd25d1bd4bf0ae
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    ff_aac_ec_data_dec returned 0
    VERIFY_EXIT=0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
