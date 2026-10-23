# Verification report: pr_review_OSSFUZZ-397731127

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: OutOfBoundsRead
- **Intro commit**: `11a8e0a4e585c0a5acf09397e39bccf45e1ba7ae`
- **Intro parent**: `a4630d479a54058f5abfd56fdcfd0b454e5de0ee`
- **Fix commit**: `d643a5ba0836c4d7ec86cb67fae387984ef3d1a6`
- **Affected files**: ['libavcodec/aac/aacdec_usac.c', 'libavcodec/aac/aacdec_dsp_template.c']

## PoC
- source: agent-generated (initial source: incomplete)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/ffmpeg/5b1ef016f604ba4aa41f/attempts/01/pocs/ffmpeg/OSSFUZZ-397731127`
- input: `crash_dq_part3.bin` (94 bytes)
- run.sh: True

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- run_poc on post_intro crashed (crashed=True): AddressSanitizer global-buffer-overflow, READ of size 4, 28 bytes to the left of global variable ff_aac_pow2sf_tab, in dequant_scalefactors (libavcodec/aac/aacdec_dsp_template.c:73), reached via spectrum_scale→spectrum_decode→decode_usac_core_coder→ff_aac_usac_decode_frame→aac_decode_frame_int→latm_decode_frame→avcodec_send_packet. This is exactly the scenario the fix's `FFMAX(sce->sfo[...] + noise_offset, -200)` clamp in apply_noise_fill (aacdec_usac.c) exists to prevent: the intro commit moved noise-offset accumulation from the safe float sce->sf onto the raw integer sce->sfo with no lower bound, and sfo[idx] here evaluates to about -207 (200-207 = -7, i.e. 28 bytes = 7 floats before the table start), so ff_aac_pow2sf_tab[sfo[idx]+POW_SF2_ZERO] reads out of bounds. run_poc on pre_intro with the identical input/harness completed cleanly (exit=0, crashed=False, "pixels decoded: 40960, samples decoded: 38912, iterations: 38", no sanitizer report). run_poc on post_benign with the identical input/harness likewise completed cleanly (exit=0, crashed=False, identical decode counts, no sanitizer report). The reproducer input was discovered by hand-deriving the AAC-USAC/LATM bitstream syntax from aacdec_latm.h/aacdec_usac.c to build a valid seed reaching decode_usac_core_coder→apply_noise_fill→dequant_scalefactors, then running a short guided-fuzzing session (libFuzzer fork mode) from that seed against the post_intro build of the same harness; the resulting crash was isolated and its bytes verified identical (md5/cmp) before being split into /poc/crash_dq_part0..3.bin. The same exact input and harness invocation was used unmodified across all three revisions (pre_intro/post_intro/post_benign) via run_poc, satisfying the invariance requirement: sanitizer report present only in post_intro, absent in pre_intro and post_benign.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=a4630d479a54  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=972237c7ace482b9ac566defe42826d6fc472df4679a66a7b856f241a42fcc5f
  source_integrity=True
  output_tail:
                ^~~~~~~
    tools/target_dec_fuzzer.c:393:21: warning: 522 enumeration values not handled in switch: 'AV_CODEC_ID_NONE', 'AV_CODEC_ID_MPEG1VIDEO', 'AV_CODEC_ID_MPEG2VIDEO'... [-Wswitch]
                switch (ctx->codec_id) {
                        ^~~~~~~~~~~~~
    tools/target_dec_fuzzer.c:407:21: warning: 518 enumeration values not handled in switch: 'AV_CODEC_ID_NONE', 'AV_CODEC_ID_MPEG1VIDEO', 'AV_CODEC_ID_MPEG2VIDEO'... [-Wswitch]
                switch (ctx->codec_id) {
                        ^~~~~~~~~~~~~
    5 warnings generated.
    INFO: Running with entropic power schedule (0xFF, 100).
    INFO: Seed: 3299635486
    INFO: Loaded 1 modules   (316 inline 8-bit counters): 316 [0x55c4b9230240, 0x55c4b923037c), 
    INFO: Loaded 1 PC tables (316 PCs): 316 [0x55c4b9230380,0x55c4b9231740), 
    /work/aac_latm_fuzzer_run: Running 1 inputs 1 time(s) each.
    Running: /tmp/crash_input.bin
    pixels decoded: 40960, samples decoded: 38912, iterations: 38
    Executed /tmp/crash_input.bin in 3 ms
    ***
    *** NOTE: fuzzing was not performed, you have only
    ***       executed the target code on a fixed set of inputs.
    ***
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=1  poc_ran=True  patched=False
  commit=11a8e0a4e585  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=972237c7ace482b9ac566defe42826d6fc472df4679a66a7b856f241a42fcc5f
  source_integrity=True
  sanitizer:
    316 [0x5633d2db5380,0x5633d2db6740), 
    /work/aac_latm_fuzzer_run: Running 1 inputs 1 time(s) each.
    Running: /tmp/crash_input.bin
    =================================================================
    ==13==ERROR: AddressSanitizer: global-buffer-overflow on address 0x5633d3c4d2e4 at pc 0x5633d1ef7bcf bp 0x7fffbcd39b90 sp 0x7fffbcd39b88
    READ of size 4 at 0x5633d3c4d2e4 thread T0
        #0 0x5633d1ef7bce in dequant_scalefactors /work/libavcodec/aac/aacdec_dsp_template.c:73:28
        #1 0x5633d1f0ce8c in spectrum_scale /work/libavcodec/aac/aacdec_usac.c:991:5
        #2 0x5633d1f0ce8c in spectrum_decode /work/libavcodec/aac/aacdec_usac.c:1236:9
        #3 0x5633d1f0ce8c in decode_usac_core_coder /work/libavcodec/aac/aacdec_usac.c:1417:5
        #4 0x5633d1f07ed9 in ff_aac_usac_decode_frame /work/libavcodec/aac/aacdec_usac.c
        #5 0x5633d1ee79e6 in aac_decode_frame_int /work/libavcodec/aac/aacdec.c:2430:15
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=a4630d479a54  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=972237c7ace482b9ac566defe42826d6fc472df4679a66a7b856f241a42fcc5f
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
                ^~~~~~~
    tools/target_dec_fuzzer.c:393:21: warning: 522 enumeration values not handled in switch: 'AV_CODEC_ID_NONE', 'AV_CODEC_ID_MPEG1VIDEO', 'AV_CODEC_ID_MPEG2VIDEO'... [-Wswitch]
                switch (ctx->codec_id) {
                        ^~~~~~~~~~~~~
    tools/target_dec_fuzzer.c:407:21: warning: 518 enumeration values not handled in switch: 'AV_CODEC_ID_NONE', 'AV_CODEC_ID_MPEG1VIDEO', 'AV_CODEC_ID_MPEG2VIDEO'... [-Wswitch]
                switch (ctx->codec_id) {
                        ^~~~~~~~~~~~~
    5 warnings generated.
    INFO: Running with entropic power schedule (0xFF, 100).
    INFO: Seed: 3737827382
    INFO: Loaded 1 modules   (316 inline 8-bit counters): 316 [0x55bcb636c240, 0x55bcb636c37c), 
    INFO: Loaded 1 PC tables (316 PCs): 316 [0x55bcb636c380,0x55bcb636d740), 
    /work/aac_latm_fuzzer_run: Running 1 inputs 1 time(s) each.
    Running: /tmp/crash_input.bin
    pixels decoded: 40960, samples decoded: 38912, iterations: 38
    Executed /tmp/crash_input.bin in 3 ms
    ***
    *** NOTE: fuzzing was not performed, you have only
    ***       executed the target code on a fixed set of inputs.
    ***
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
