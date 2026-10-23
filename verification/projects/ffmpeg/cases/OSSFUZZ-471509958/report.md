# Verification report: pr_review_OSSFUZZ-471509958

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: BufferOverflow
- **Intro commit**: `30fc5b1baaa0823f134768823ab6695211d0fe21`
- **Intro parent**: `58c0711fca17cb5231506c63f63a2aa5568a4997`
- **Fix commit**: `65fd5167686e8cf8489a271bf22fa9dc8c818a70`
- **Affected files**: ['libavcodec/adpcm.c']

## PoC
- source: agent-generated (initial source: incomplete)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/ffmpeg/8d49efece595b6c3a23c/attempts/01/pocs/ffmpeg/OSSFUZZ-471509958`
- input: `input.bin` (1092 bytes)
- run.sh: False

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- post_intro (commit 30fc5b1baaa0): run_poc reproducibly aborts with "AddressSanitizer: heap-buffer-overflow ... WRITE of size 2 ... #0 adpcm_decode_frame /work/libavcodec/adpcm.c:1730:5", i.e. an out-of-bounds write directly at the ADPCM_IMA_MAGIX CASE into the get_buffer2-allocated audio frame — this matches the original OSS-Fuzz report ("Crash Type: Heap-buffer-overflow WRITE 2", crash state "adpcm_decode_frame") and the meta.json root cause: the MAGIX case unconditionally writes two interleaved samples per iteration (status[0]/status[1]) with the inner-loop bound tied to avctx->block_align instead of the sample count actually allocated for the (mono) output frame, and mono is never rejected. pre_intro (commit 58c0711fca17): the same driver, same command, same input cleanly prints "DECODER_NOT_FOUND" (exit 0, no crash) — avcodec_find_decoder_by_name("adpcm_ima_magix") returns NULL because the ADPCM_IMA_MAGIX decoder (and its AV_CODEC_ID) does not exist at all before the intro commit (confirmed independently: the enum/decoder symbol is entirely absent from pre_intro's source and library). This is a clean, real program execution (not a build/link failure) that unambiguously shows the vulnerable feature, and therefore the bug, was introduced together by the intro commit. post_benign: the same command/input completes cleanly (exit 0): the decoder now explicitly detects the mono case and reports "mono ADPCM Magix is not implemented ... invalid number of samples in packet", returns an error from avcodec_send_packet, and never reaches the overflowing write path — matching the discussion's statement "we ask for a mono sample because the implementation for mono is incomplete". No ASan report on pre_intro or post_benign; a clear, reproducible ASan heap-buffer-overflow WRITE only on post_intro, under the exact same reproducer, confirms both intro_verified=yes and benign_verified=yes.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=58c0711fca17  note=build cached
  command=ASAN_OPTIONS=detect_leaks=0 /work/poc_bin2 $INPUT
  poc_sha256=e405ff87f8e2eac2752d6aead3832a37053445f6b98b45977826c92941a270f8
  source_integrity=True
  output_tail:
    VERIFY_EXIT=0
    
    DECODER_NOT_FOUND
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=1  poc_ran=True  patched=False
  commit=30fc5b1baaa0  note=build cached
  command=ASAN_OPTIONS=detect_leaks=0 /work/poc_bin2 $INPUT
  poc_sha256=e405ff87f8e2eac2752d6aead3832a37053445f6b98b45977826c92941a270f8
  source_integrity=True
  sanitizer:
    VERIFY_EXIT=1
    
    =================================================================
    ==8==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x612000000140 at pc 0x5625cf17004a bp 0x7ffd85077110 sp 0x7ffd85077108
    WRITE of size 2 at 0x612000000140 thread T0
        #0 0x5625cf170049 in adpcm_decode_frame /work/libavcodec/adpcm.c:1730:5
        #1 0x5625ce30a7d9 in decode_simple_internal /work/libavcodec/decode.c:440:16
        #2 0x5625ce30a7d9 in decode_simple_receive_frame /work/libavcodec/decode.c:600:15
        #3 0x5625ce30a7d9 in ff_decode_receive_frame_internal /work/libavcodec/decode.c:636:15
        #4 0x5625ce30c218 in decode_receive_frame_internal /work/libavcodec/decode.c:653:15
        #5 0x5625ce30c0a8 in avcodec_send_packet /work/libavcodec/decode.c:729:15
        #6 0x5625ce0a8478 in main (/work/poc_bin2+0x514478) (BuildId: af0c78a656027e8bb3040e57a5ca789508ec36eb)
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=58c0711fca17  note=build cached
  command=ASAN_OPTIONS=detect_leaks=0 /work/poc_bin2 $INPUT
  poc_sha256=e405ff87f8e2eac2752d6aead3832a37053445f6b98b45977826c92941a270f8
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    VERIFY_EXIT=0
    
    [adpcm_ima_magix @ 0x618000000080] mono ADPCM Magix is not implemented. Update your FFmpeg version to the newest one from Git. If the problem still occurs, it means that your file has a feature which has not been implemented.
    [adpcm_ima_magix @ 0x618000000080] If you want to help, upload a sample of this file to https://streams.videolan.org/upload/ and contact the ffmpeg-devel mailing list. (ffmpeg-devel@ffmpeg.org)
    [adpcm_ima_magix @ 0x618000000080] invalid number of samples in packet
    send_packet ret=-1094995529
    DONE_NO_CRASH
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
