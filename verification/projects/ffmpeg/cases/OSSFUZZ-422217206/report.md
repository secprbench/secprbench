# Verification report: pr_review_OSSFUZZ-422217206

- **Status**: `inconclusive`
- **Intro verified**: None
- **Benign verified**: None
- **Bug type**: UninitializedMemory
- **Intro commit**: `d4556c98f02e4f2d3deb86efeb060ebe4659be96`
- **Intro parent**: `2de0d095b84f5dea1201ba06933f2a3f42d9a5dc`
- **Fix commit**: `a45755e302baf56461bd7d8cf0c3a88c0ee5e83f`
- **Affected files**: ['libavcodec/dxvenc.c']

## PoC
- source: agent-generated (initial source: incomplete)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/ffmpeg/27f80a6225e83fd521e8/attempts/05/pocs/ffmpeg/OSSFUZZ-422217206`
- input: `None` (0 bytes)
- run.sh: True

## Findings

- The agent claim lacks a matching admissible three-version oracle.
- Source inspection across the three revisions confirms the mechanism. pre_intro's dxv_init() only accepts width/height that are multiples of TEXTURE_BLOCK_W/H(4) and has no padding/safe_data code path at all, so it cannot exhibit this bug. The intro commit (d4556c98f02e) added support for widths not aligned to DXV_ALIGN(16) by allocating a padded 'safe_data' buffer via av_image_alloc(), copying the real WxH pixels with av_image_copy2() (which copies exactly width*4 bytes per row, not frame->linesize[0] bytes), then trying to zero the pad columns with memset(safe_data+y*safe_linesize+frame->linesize[0], 0, safe_linesize-frame->linesize[0]). When the source frame's own row stride (frame->linesize[0]) exceeds the true pixel-row width (width*4) -- which happens whenever the source frame buffer's alignment padding doesn't coincide with DXV's own alignment -- the byte range [width*4, frame->linesize[0]) of the freshly malloc'd safe_data buffer is written by neither the copy nor this memset, and is later read by the texture compressor. This is precisely the crash state reported upstream (compress_color / dxt1_block / exec_func) and precisely what the fix commit's message describes ('Clear width to linesize not linesize to linesize'): it changes the memset start offset from frame->linesize[0] to 4*avctx->width, covering the whole pad region regardless of the source frame's own stride padding.

Built and ran the identical PoC/harness via run_poc against all three revisions, each freshly built from scratch inside its container with clang -fsanitize=memory -fsanitize-memory-track-origins=2 (minimal component set: avcodec/avformat/avutil/swresample/avfilter, dxv encoder + rawvideo decoder only) -- required because this is a pure use-of-uninitialized-value on otherwise in-bounds heap memory, a class only MemorySanitizer (not ASan) can observe, matching the original OSS-Fuzz job (libfuzzer_msan_ffmpeg). MSAN_OPTIONS=abort_on_error=1 is set so a detected report raises SIGABRT (a real crash) rather than a plain exit(1).
 - pre_intro: run_poc exit=0, crashed=False, ends with 'linesize=96 width*4=80 / got packet size=28 / done'. Bug absent, as expected (no padding path exists pre-intro).
 - post_intro: run_poc exit=134, crashed=True. MemorySanitizer 'use-of-uninitialized-value' fires with stack constant_color -> compress_color -> dxt1_block -> exec_func -> ff_texturedsp_exec_compress_threads -> dxv_encode (dxvenc.c:220) -> ... -> avcodec_send_frame -> main, with the 'Uninitialized value was created by a heap allocation' trace pointing to av_malloc -> av_image_alloc -> dxv_encode (dxvenc.c:184) -- exactly the safe_data buffer from the intro commit's new padding code. This exactly matches the OSS-Fuzz reported crash state (compress_color / dxt1_block / exec_func).
 - post_benign: run_poc exit=0, crashed=False, identical clean tail 'linesize=96 width*4=80 / got packet size=28 / done' (same output size as pre_intro) -- the fix's corrected memset boundary eliminates the uninitialized read.

The same width/height/pix_fmt/frame-alignment invocation (poc.c, unchanged) was used for all three revisions; only the underlying source revision differed, satisfying the invariant-reproducer requirement.

## Agent oracle

- machine gate: inconclusive (unproven)
- basis: The agent claim lacks a matching admissible three-version oracle.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=2de0d095b84f  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=b1f0a5485af48f7edaadb90e0d146a997f314e5678b771b82590c2b702b50075
  source_integrity=True
  output_tail:
    CC	libavfilter/vf_format.o
    CC	libavfilter/vf_hflip.o
    CC	libavfilter/vf_null.o
    CC	libavfilter/vf_rotate.o
    CC	libavfilter/vf_transpose.o
    CC	libavfilter/vf_vflip.o
    CC	libavfilter/video.o
    AR	libavcodec/libavcodec.a
    AR	libswresample/libswresample.a
    AR	libavfilter/libavfilter.a
    AR	libavformat/libavformat.a
    AR	libavutil/libavutil.a
    COMPILE_DONE
    === RUN ===
    RUN_RET=0
    VERIFY_EXIT=0
    
    linesize=96 width*4=80
    got packet size=28
    done
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=d4556c98f02e  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=b1f0a5485af48f7edaadb90e0d146a997f314e5678b771b82590c2b702b50075
  source_integrity=True
  crash_output:
        #3 0x55b76fe99ce7 in dxv_encode /tmp/msan-src/libavcodec/dxvenc.c:184:19
        #4 0x55b76fe9e512 in ff_encode_encode_cb /tmp/msan-src/libavcodec/encode.c:239:11
        #5 0x55b76fea02a4 in encode_simple_internal /tmp/msan-src/libavcodec/encode.c:325:15
        #6 0x55b76fea02a4 in encode_simple_receive_packet /tmp/msan-src/libavcodec/encode.c:339:15
        #7 0x55b76fea02a4 in encode_receive_packet_internal /tmp/msan-src/libavcodec/encode.c:373:15
        #8 0x55b76fe9f620 in avcodec_send_frame /tmp/msan-src/libavcodec/encode.c:516:15
        #9 0x55b76fe768ff in main /poc/poc.c:29:15
        #10 0x7f7dd98d5d8f in __libc_start_call_main csu/../sysdeps/nptl/libc_start_call_main.h:58:16
    
    SUMMARY: MemorySanitizer: use-of-uninitialized-value /tmp/msan-src/libavcodec/texturedspenc.c:447:17 in constant_color
    Exiting
    /poc/run.sh: line 44:  3755 Aborted                 /tmp/poc_msan
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=2de0d095b84f  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=b1f0a5485af48f7edaadb90e0d146a997f314e5678b771b82590c2b702b50075
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    CC	libavfilter/vf_format.o
    CC	libavfilter/vf_hflip.o
    CC	libavfilter/vf_null.o
    CC	libavfilter/vf_rotate.o
    CC	libavfilter/vf_transpose.o
    CC	libavfilter/vf_vflip.o
    CC	libavfilter/video.o
    AR	libavcodec/libavcodec.a
    AR	libswresample/libswresample.a
    AR	libavfilter/libavfilter.a
    AR	libavformat/libavformat.a
    AR	libavutil/libavutil.a
    COMPILE_DONE
    === RUN ===
    RUN_RET=0
    VERIFY_EXIT=0
    
    linesize=96 width*4=80
    got packet size=28
    done
```

## Interpretation

The available evidence does not establish both labels. Inspect the findings and per-version results for the limiting reason.
