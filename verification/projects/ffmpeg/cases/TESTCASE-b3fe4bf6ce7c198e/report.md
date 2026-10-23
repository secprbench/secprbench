# Verification report: pr_review_TESTCASE-b3fe4bf6ce7c198e

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: OutOfBoundsRead
- **Intro commit**: `baad75cafa6bac298b72c177f657a2eb8e31cff1`
- **Intro parent**: `86977fdb6bb0ba553a9c654309eb9c028a3777b4`
- **Fix commit**: `ddcb9dd3b5d21d055774abd61ae609ecb728cb1c`
- **Affected files**: ['libavcodec/aac/aacdec_usac.c']

## PoC
- source: agent-generated (initial source: no_poc)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/ffmpeg/5c04d98c28079578f32b/attempts/07/pocs/ffmpeg/TESTCASE-b3fe4bf6ce7c198e`
- input: `None` (0 bytes)
- run.sh: True

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- Root cause confirmed by source diff: introducing commit baad75cafa6b ("aacdec_usac: add support for parsing Mpsp212") added aacdec_usac_mps212.c/.h and parse_mps212(), which consume e->mps.otts_bands_phase (a raw 5-bit bitstream field, max 31) as an unclamped `end_band` array-bound parameter passed into ff_aac_ec_data_dec() for the IPD ("phase") data set, while the only validation present (mps_fr_nb_bands[freq_res], max 28) bounds a *different*, correctly-used `nb_bands` for the CLD/ICC data sets. The companion fix (ddcb9dd3b5d2, = post_benign) adds `if (otts_bands_phase > numBands) return AVERROR_INVALIDDATA;` (and the analogous check for bsResidualBands) directly in decode_usac_element_pair(), rejecting the malformed config before the bad value can ever reach parse_mps212().

No existing PoC/container-level reproducer was available, and hand-building a full valid USAC/xHE-AAC bitstream (AudioSpecificConfig + SBR header + arithmetic-coded core spectral data, all of which must be correctly parsed before parse_mps212 is ever reached in the real decode path) was infeasible relative to directly exercising the two functions the bug actually lives in. I therefore drove the real, unmodified vulnerable functions (via source #include of the untouched target .c file, not a rewritten copy) with a minimal, precisely bit-level-designed GetBitContext that reproduces exactly what the real bitstream fields would contain for this scenario. run_poc via the SAME run.sh/input on all three configured versions shows: (1) pre_intro accepts the same unchecked value at the config stage (ret=0) but the vulnerable sink is structurally absent (confirmed both by a failed compile and by grep); (2) post_intro accepts the same config and crashes deterministically under AddressSanitizer with a stack-buffer-overflow exactly where the root-cause description says the bound is missing; (3) post_benign rejects the same out-of-range config value before the sink is ever reached, and does not crash. A negative control with an in-bounds value (28) produces no crash on post_intro, isolating the defect to the out-of-range field rather than to the harness itself. The sanitizer fires as a stack WRITE overflow rather than literally as a "read," but per the ground rules a sanitizer report establishing the same regression under the same reproducer is accepted even when the precise sub-type label is imprecise; the underlying defect (missing bounds check on bsOttBandsPhase/bsResidualBands used as an array bound, exactly as described in meta.json's root_cause and findings) is unambiguously introduced by baad75cafa6b and fixed by the benign commit.

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
  poc_sha256=455abe962d8dbc014153b68a858b77599c584104b1945eee1438d2e0aaf8fb18
  source_integrity=True
  output_tail:
    === Attempting harness_frame.c (config stage + parse_mps212 frame stage) ===
    === Build FAILED: parse_mps212()/AACUsacMPSData are absent in this revision ===
    --- compiler output (expected on pre-intro) ---
    /poc/harness_frame.c:111:5: error: unknown type name 'AACUsacMPSData'; did you mean 'AACUsacElemData'?
        AACUsacMPSData mps; memset(&mps, 0, sizeof(mps));
        ^~~~~~~~~~~~~~
        AACUsacElemData
    /work/libavcodec/aac/aacdec.h:157:3: note: 'AACUsacElemData' declared here
    } AACUsacElemData;
      ^
    1 error generated.
    === Falling back to harness_config_pre.c (config-stage only) ===
    RESULT ret=0 freq_res=1 otts_bands_phase=31 phase_coding=1 residual_coding=0 stereo_config_index=1
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=baad75cafa6b  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=455abe962d8dbc014153b68a858b77599c584104b1945eee1438d2e0aaf8fb18
  source_integrity=True
  sanitizer:
    rness_frame.c (config stage + parse_mps212 frame stage) ===
    === Build OK: parse_mps212()/AACUsacMPSData are present in this revision ===
    CONFIG ret=0 otts_bands_phase=31
    Calling parse_mps212() now; a stack-buffer-overflow under ASan is expected in the vulnerable (post_intro) build.
    VERIFY_EXIT=134
    
    =================================================================
    ==12==ERROR: AddressSanitizer: stack-buffer-overflow on address 0x7ffc317ef488 at pc 0x55b127bce62a bp 0x7ffc317ef350 sp 0x7ffc317ef348
    WRITE of size 2 at 0x7ffc317ef488 thread T0
        #0 0x55b127bce629 in ec_pair_dec /work/libavcodec/aac/aacdec_usac_mps212.c
        #1 0x55b127bce629 in ff_aac_ec_data_dec /work/libavcodec/aac/aacdec_usac_mps212.c:646:19
        #2 0x55b127b8a41e in parse_mps212 /work/libavcodec/aac/aacdec_usac.c:1444:19
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=86977fdb6bb0  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=455abe962d8dbc014153b68a858b77599c584104b1945eee1438d2e0aaf8fb18
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    === Attempting harness_frame.c (config stage + parse_mps212 frame stage) ===
    === Build OK: parse_mps212()/AACUsacMPSData are present in this revision ===
    CONFIG ret=-1094995529 otts_bands_phase=0
    RESULT config-stage rejected out-of-range value; frame stage not reached (matches real decoder control flow)
    VERIFY_EXIT=0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
