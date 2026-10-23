# Verification report: pr_review_TESTCASE-392550fb9400b0c0

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: BufferOverflow
- **Intro commit**: `baad75cafa6bac298b72c177f657a2eb8e31cff1`
- **Intro parent**: `86977fdb6bb0ba553a9c654309eb9c028a3777b4`
- **Fix commit**: `770bc1c23a18fe72874e888e1be123a21620acb5`
- **Affected files**: ['libavcodec/aac/aacdec_usac_mps212.c']

## PoC
- source: agent-generated (initial source: no_poc)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/ffmpeg/18dca4d7126e7c416325/attempts/01/pocs/ffmpeg/TESTCASE-392550fb9400b0c0`
- input: `extradata.bin` (10 bytes)
- run.sh: True

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- Verified by direct reproduction using run_poc on all three configured versions with the byte-identical PoC (/poc/run.sh, /poc/harness.c, /poc/extradata.bin, /poc/frame.bin). meta.json's root cause is that ff_aac_ec_data_dec() in libavcodec/aac/aacdec_usac_mps212.c calls get_freq_strides() with ld->freq_res (declared int16_t freq_res[MPS_MAX_PARAM_SETS==9]) used simultaneously as the input bsFreqRes selector for the current parameter set and as the output scratch buffer, which get_freq_strides always fills starting at absolute index 0 regardless of which parameter set is active, corrupting freq_res entries belonging to other parameter sets and writing beyond the declared 9-slot bound. Since no existing PoC/testcase reproduced this (the fix commit's own message says "testcase exists but did not replicate for me", and meta.json records source="no_poc"), I hand-built a complete AAC-USAC (xHE-AAC) AudioSpecificConfig and one access unit bit-by-bit from the USAC/MPS-212 parsing source (config: object_type=42, SBR-enabled CPE with stereoConfigIndex=1; frame: 1 core channel with max_sfb=0 so scale factors/spectrum need no extra bits, minimal SBR grid/envelope/noise fields with n_q=1 via bs_noise_bands=0, then 2 OTT-CLD parameter sets both with data_mode=3 and bsFreqRes=2), verifying intermediate state (nb_param_sets=2, code reaching ff_aac_ec_data_dec/ff_aac_map_index_data) with gdb before finalizing. Running this exact reproducer through run_poc: post_intro crashes deterministically with a genuine AddressSanitizer global-buffer-overflow read exactly at the aliasing-corrupted `stride_table[ld->freq_res[set_idx]]` access described by the root cause; pre_intro does not crash because USAC MPS-212 support (and thus the buggy function) does not exist yet at that revision (clean AVERROR_PATCHWELCOME, "not implemented"); post_benign does not crash because the fix (introducing a temporary `freq_stride_map` array instead of reusing ld->freq_res as output) removes the aliasing, confirmed both by the absence of any crash and by reading the fixed source. This cleanly establishes intro_verified=yes and benign_verified=yes for this BufferOverflow bug.

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
  poc_sha256=996749dcde965eea0dd10d293b1e833b613129c15275dd2045bb24701db67180
  source_integrity=True
  output_tail:
    _c - type: fft_float, len: 128, factor: 2, flags: [unaligned, inplace, out_of_place, preshuf]
    Transform tree:
        mdct_pfa_15xM_inv_float_c - type: mdct_float, len: 960, factors[2]: [15, any], flags: [unaligned, out_of_place, inv_only]
            fft32_ns_float_c - type: fft_float, len: 32, factor: 2, flags: [unaligned, inplace, out_of_place, preshuf]
    Transform tree:
        mdct_inv_float_c - type: mdct_float, len: 1024, factors[2]: [2, any], flags: [unaligned, out_of_place, inv_only]
            fft512_ns_float_c - type: fft_float, len: 512, factor: 2, flags: [unaligned, inplace, out_of_place, preshuf]
    Transform tree:
        mdct_fwd_float_c - type: mdct_float, len: 1024, factors[2]: [2, any], flags: [unaligned, out_of_place, fwd_only]
            fft512_ns_float_c - type: fft_float, len: 512, factor: 2, flags: [unaligned, inplace, out_of_place, preshuf]
    avcodec_open2 -> 0
    opened: sample_rate=48000 channels=2 object_type via profile=41
    [aac @ 0x618000000080] AAC USAC Mps212 is not implemented. Update your FFmpeg version to the newest one from Git. If the problem still occurs, it means that your file has a feature which has not been implemented.
    send_packet -> -1163346256
    receive_frame -> -11
    done
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=1  poc_ran=True  patched=False
  commit=baad75cafa6b  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=996749dcde965eea0dd10d293b1e833b613129c15275dd2045bb24701db67180
  source_integrity=True
  sanitizer:
     [unaligned, inplace, out_of_place, preshuf]
    avcodec_open2 -> 0
    opened: sample_rate=48000 channels=2 object_type via profile=41
    =================================================================
    ==12==ERROR: AddressSanitizer: global-buffer-overflow on address 0x55f5ab7d6bb0 at pc 0x55f5aad303a8 bp 0x7ffd269dd690 sp 0x7ffd269dd688
    READ of size 4 at 0x55f5ab7d6bb0 thread T0
        #0 0x55f5aad303a7 in ff_aac_map_index_data /work/libavcodec/aac/aacdec_usac_mps212.c:831:22
        #1 0x55f5aad211ce in parse_mps212 /work/libavcodec/aac/aacdec_usac.c:1425:5
        #2 0x55f5aad211ce in decode_usac_core_coder /work/libavcodec/aac/aacdec_usac.c:1650:15
        #3 0x55f5aad1c073 in ff_aac_usac_decode_frame /work/libavcodec/aac/aacdec_usac.c
        #4 0x55f5aacfb92d in aac_decode_frame_int /work/libavcodec/aac/aacdec.c:2454:15
        #5 0x55f5aacf229b in aac_decode_frame /work/libavcodec/aac/aacdec.c:2521:15
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=86977fdb6bb0  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=996749dcde965eea0dd10d293b1e833b613129c15275dd2045bb24701db67180
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
     preshuf]
    Transform tree:
        mdct_pfa_3xM_inv_float_c - type: mdct_float, len: 768, factors[2]: [3, any], flags: [unaligned, out_of_place, inv_only]
            fft128_ns_float_c - type: fft_float, len: 128, factor: 2, flags: [unaligned, inplace, out_of_place, preshuf]
    Transform tree:
        mdct_pfa_15xM_inv_float_c - type: mdct_float, len: 960, factors[2]: [15, any], flags: [unaligned, out_of_place, inv_only]
            fft32_ns_float_c - type: fft_float, len: 32, factor: 2, flags: [unaligned, inplace, out_of_place, preshuf]
    Transform tree:
        mdct_inv_float_c - type: mdct_float, len: 1024, factors[2]: [2, any], flags: [unaligned, out_of_place, inv_only]
            fft512_ns_float_c - type: fft_float, len: 512, factor: 2, flags: [unaligned, inplace, out_of_place, preshuf]
    Transform tree:
        mdct_fwd_float_c - type: mdct_float, len: 1024, factors[2]: [2, any], flags: [unaligned, out_of_place, fwd_only]
            fft512_ns_float_c - type: fft_float, len: 512, factor: 2, flags: [unaligned, inplace, out_of_place, preshuf]
    avcodec_open2 -> 0
    opened: sample_rate=48000 channels=2 object_type via profile=41
    [aac @ 0x618000000080] element type mismatch 1 != 0
    send_packet -> 0
    receive_frame -> 0
    done
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
