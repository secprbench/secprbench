# Verification report: pr_review_OSSFUZZ-421954767

- **Status**: `inconclusive`
- **Intro verified**: None
- **Benign verified**: None
- **Bug type**: UninitializedMemory
- **Intro commit**: `80606442377a7bca9501e2612e9a44b5044316ca`
- **Intro parent**: `507c2a57746d503cd97e1dd520e563a1f1b85fee`
- **Fix commit**: `909229b880d5f2c2277ab10915954b18d5162322`
- **Affected files**: ['libavcodec/shorten.c']

## PoC
- source: agent-generated (initial source: incomplete)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/ffmpeg/3e0e5056d0a3083c76f3/attempts/01/pocs/ffmpeg/OSSFUZZ-421954767`
- input: `None` (0 bytes)
- run.sh: True

## Findings

- The agent claim lacks a matching admissible three-version oracle.
- The configured Docker build only compiles with AddressSanitizer, which cannot detect a pure uninitialized-value read, and the deterministic fast-path found no usable PoC (this bug type is UninitializedMemory / MSAN-only; oss-fuzz Job Type libfuzzer_msan_ffmpeg). I built, for each of pre_intro/post_intro/post_benign, a scratch MemorySanitizer configuration of ffmpeg (avcodec/avformat/avutil/swresample + shorten decoder only, for build speed) from an UNMODIFIED copy of that version's already-checked-out /work tree -- the tracked source used by build_version/run_poc itself was never edited; only a throwaway copy under /work/_msan_src was built/instrumented, and no shared dependency cache was altered. /poc/run.sh (invoked through the standard run_poc tool) regenerates the crafted PoC from /poc/gen_poc.py and runs it through that pre-built MSAN driver (falling back to the plain ASAN ffmpeg binary if the MSAN driver is ever absent).

I derived the crafted 16446-byte input from the diff/root-cause: pre_intro clears AV_INPUT_BUFFER_PADDING_SIZE bytes after the valid data on every decode_frame call (always safe regardless of av_fast_realloc's rounding). The intro commit (80606442) deleted that per-call clear and replaced it with a one-time memset sized from the OLD/NEW *nominal* max_framesize values instead of the actual allocated_bitstream_size that av_fast_realloc reports; since av_fast_realloc over-allocates by ~1/16+32 bytes, the real allocation ends up bigger than nominal_max_framesize+padding, leaving a genuine unzeroed gap. The fix (post_benign / 909229b8) tracks old/new allocated_bitstream_size explicitly and clears exactly the newly-grown region, closing that gap. My PoC forces that growth (8192->16384 nominal / ~8804->~17508 actual) and then decodes one deliberately dense audio block so the golomb reader's cursor reaches the tail of the declared window and its lookahead crosses into the unzeroed region.

Running this exact input through run_poc's own /poc/run.sh on all three configured revisions: post_intro's process aborts (exit=134, crashed=True) with "MemorySanitizer: use-of-uninitialized-value" in get_ur_golomb_jpegls, reached via get_sr_golomb_shorten <- decode_subframe_lpc (shorten.c:396) <- shorten_decode_frame (shorten.c:711) <- decode_simple_internal/ff_decode_receive_frame_internal -- an exact match (identical 3-frame crash state, identical MSAN sanitizer, identical Crash Type) to the tracked oss-fuzz report, with the allocation-origin trace pointing directly at the buggy av_fast_realloc call inside shorten_decode_frame (shorten.c:590). pre_intro and post_benign, run via the identical run_poc/run.sh path with the identical regenerated input, both cleanly exit 0 (crashed=False), decode frame 1 successfully, and show no sanitizer report. The SAME command (/poc/run.sh, unmodified across versions) and the SAME input were used for pre_intro, post_intro and post_benign, and pre_intro/post_benign execute the identical code path (buffer growth + first audio block decode) without ever triggering the report -- this is specific to the intro commit's clearing logic, not a pre-existing or generic condition: introduction=yes, benign(fix)=yes.

## Agent oracle

- machine gate: inconclusive (unproven)
- basis: The agent claim lacks a matching admissible three-version oracle.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=507c2a57746d  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=63ae74ba8c2cb5761dbd5eb616a2e9c25cc5b5e232a33c0ce1b7e3cf0741d8d0
  source_integrity=True
  output_tail:
    VERIFY_EXIT=0
    
    [shorten @ 0x717000000000] overread: 1
    send_packet ret=-1094995529
    got frame 1 nb_samples=2048
    EOF, done. total frames=1
    done, total frames=1
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=80606442377a  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=63ae74ba8c2cb5761dbd5eb616a2e9c25cc5b5e232a33c0ce1b7e3cf0741d8d0
  source_integrity=True
  crash_output:
        #2 0x5605d91abc5e in av_fast_realloc /work/_msan_src/libavutil/mem.c:515:11
        #3 0x5605d915e574 in shorten_decode_frame /work/_msan_src/libavcodec/shorten.c:590:23
        #4 0x5605d912b49f in decode_simple_internal /work/_msan_src/libavcodec/decode.c:435:16
        #5 0x5605d912b49f in decode_simple_receive_frame /work/_msan_src/libavcodec/decode.c:605:15
        #6 0x5605d912b49f in ff_decode_receive_frame_internal /work/_msan_src/libavcodec/decode.c:641:15
        #7 0x5605d912dd9e in decode_receive_frame_internal /work/_msan_src/libavcodec/decode.c:658:15
        #8 0x5605d912dadb in avcodec_send_packet /work/_msan_src/libavcodec/decode.c:745:15
        #9 0x5605d911a669 in main /work/_msan_src/poc_driver.c:29:15
    
    SUMMARY: MemorySanitizer: use-of-uninitialized-value /work/_msan_src/libavcodec/golomb.h:484:9 in get_ur_golomb_jpegls
    Exiting
    /bin/bash: line 1:     8 Aborted                 bash -c 'cd /work && bash /poc/run.sh'
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=507c2a57746d  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=63ae74ba8c2cb5761dbd5eb616a2e9c25cc5b5e232a33c0ce1b7e3cf0741d8d0
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    VERIFY_EXIT=0
    
    [shorten @ 0x717000000000] overread: 1
    send_packet ret=-1094995529
    got frame 1 nb_samples=2048
    EOF, done. total frames=1
    done, total frames=1
```

## Interpretation

The available evidence does not establish both labels. Inspect the findings and per-version results for the limiting reason.
