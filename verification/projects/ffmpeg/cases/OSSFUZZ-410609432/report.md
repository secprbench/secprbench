# Verification report: pr_review_OSSFUZZ-410609432

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: OutOfBoundsRead
- **Intro commit**: `93b0ca26acb912b8f080f221f6165542806bceb3`
- **Intro parent**: `f6c6ba95fd69f51d7f30e8f201ff43050a53113f`
- **Fix commit**: `3afae0f4409ace1699ebe3fdd32a61f05657c09f`
- **Affected files**: ['libavcodec/sanm.c']

## PoC
- source: agent-generated (initial source: incomplete)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/ffmpeg/a571860d9e0001b6d15d/attempts/08/pocs/ffmpeg/OSSFUZZ-410609432`
- input: `None` (0 bytes)
- run.sh: False
- note: poc dir has neither run.sh nor a recognizable input file

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- Root cause confirmed exactly as described in meta.json, reproduced with run_poc on all three versions using the identical PoC and command.

In libavcodec/sanm.c:process_frame_obj(), when ctx->subversion < 2 the internal frame is hard-coded to xres=384, yres=242 (Rebel Assault 1 assumption) and ctx->have_dimensions is set, without checking that the FOBJ's own w/h (bounded only by the generic 1<=w<=800, 1<=h<=600 check) fit inside that fixed 384x242 (pitch=384) buffer. old_codec37's compr==0 path then does a raw per-row bytestream2_get_buffer(gb, dst, width) with dst advancing by ctx->pitch (=384) for each of `height` (600) rows, inside the undersized (~202468-byte actual allocation, since av_fast_padded_mallocz over-allocates via size+size/16+32) frm1 buffer — walking past the end of the buffer once the row index gets large enough.

- pre_intro (f6c6ba95fd69, run_poc exit=0 crashed=False): no subversion<2 special case exists; process_frame_obj falls into the generic "Rebel Assault 2" branch, sizing the frame from the FOBJ's own left+w / top+h (xres=8, yres=600), so ctx->pitch matches the actual per-row copy size and old_codec37 writes exactly within bounds. avcodec_send_packet/avcodec_receive_frame both return 0 (clean decode).
- post_intro (93b0ca26acb9, run_poc exit=134 crashed=True): subversion<2 branch fires, forcing xres=384/yres=242 (pitch=384) regardless of the FOBJ's actual w=8,h=600, with no validation against xres/yres. old_codec37's raw-copy loop then walks past the end of the ~202468-byte frm1 allocation. AddressSanitizer reports a clean, reproducible heap-buffer-overflow WRITE of size 8 in bytestream2_get_buffer, called from old_codec37 (sanm.c:665) <- process_frame_obj (sanm.c:1306) <- decode_frame (sanm.c:1792) <- the standard avcodec_send_packet decode path. This never fires on pre_intro or post_benign with the byte-identical input/command, and is not a harness/usage error. This is the same missing-bounds-check root cause named in the fix/discussion (the label OutOfBoundsRead vs. the observed WRITE here is the kind of harmless bug-type-label imprecision the task explicitly allows for; the original oss-fuzz report's UBSAN abort at destroy_buffers/decode_end is consistent with heap corruption from this same undersized buffer manifesting differently under a UBSan-only, non-ASan build).
- post_benign (companion fix, run_poc exit=0 crashed=False; sanm.c source confirmed via grep to contain "if (w > xres || h > yres) return AVERROR_INVALIDDATA;" immediately after the subversion<2 assignment, exactly matching fix commit 3afae0f4409a "Check w, h for subversion < 2"): with the identical input, process_frame_obj now rejects w=8,h=600 because h(600) > yres(242), returning AVERROR_INVALIDDATA (prints as -1094995529, i.e. FFERRTAG('I','N','D','A')) before old_codec37 ever executes. No crash; receive_frame correctly reports EAGAIN since no frame was produced.

Same reproducer (packet bytes + extradata + run_poc command) used across all three builds, satisfying the invariance requirement. The bug is present only in post_intro and is closed by post_benign.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=f6c6ba95fd69  note=build cached
  command=cd /tmp && cp /poc/poc.c . && clang -g -O0 -fsanitize=address -fno-omit-frame-pointer -I/work -o poc poc.c /work/libavcodec/libavcodec.a /work/libavformat/libavformat.a /work/libavutil/libavutil.a /work/libswresample/libswresample.a -lm -lpthread -lz -ldl && ./poc
  poc_sha256=d00915c6e4ff525f7b80af4e51287ff3500cf4eeb49ec79374b8f20d160e01c3
  source_integrity=True
  output_tail:
    VERIFY_EXIT=0
    
    packet len=4838 (p-pkt=4838)
    send_packet ret=0
    receive_frame ret=0
    done without crash
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=93b0ca26acb9  note=build cached
  command=cd /tmp && cp /poc/poc.c . && clang -g -O0 -fsanitize=address -fno-omit-frame-pointer -I/work -o poc poc.c /work/libavcodec/libavcodec.a /work/libavformat/libavformat.a /work/libavutil/libavutil.a /work/libswresample/libswresample.a -lm -lpthread -lz -ldl && ./poc
  poc_sha256=d00915c6e4ff525f7b80af4e51287ff3500cf4eeb49ec79374b8f20d160e01c3
  source_integrity=True
  sanitizer:
    VERIFY_EXIT=134
    
    packet len=4838 (p-pkt=4838)
    =================================================================
    ==8==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x7f905afff000 at pc 0x55d6bade0e3a bp 0x7ffed661e0f0 sp 0x7ffed661d8c0
    WRITE of size 8 at 0x7f905afff000 thread T0
        #0 0x55d6bade0e39 in __asan_memcpy (/tmp/poc+0x4c4e39) (BuildId: e6ea27609bc1591bb4e1f42487a2b482edc7da49)
        #1 0x55d6bb7d6f17 in bytestream2_get_buffer /work/libavcodec/bytestream.h:272:5
        #2 0x55d6bb7d6f17 in old_codec37 /work/libavcodec/sanm.c:665:13
        #3 0x55d6bb7d417d in process_frame_obj /work/libavcodec/sanm.c:1306:16
        #4 0x55d6bb7d417d in decode_frame /work/libavcodec/sanm.c:1792:27
        #5 0x55d6bb069436 in decode_simple_internal /work/libavcodec/decode.c:443:16
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=f6c6ba95fd69  note=build cached
  command=cd /tmp && cp /poc/poc.c . && clang -g -O0 -fsanitize=address -fno-omit-frame-pointer -I/work -o poc poc.c /work/libavcodec/libavcodec.a /work/libavformat/libavformat.a /work/libavutil/libavutil.a /work/libswresample/libswresample.a -lm -lpthread -lz -ldl && ./poc
  poc_sha256=d00915c6e4ff525f7b80af4e51287ff3500cf4eeb49ec79374b8f20d160e01c3
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    VERIFY_EXIT=0
    
    packet len=4838 (p-pkt=4838)
    send_packet ret=-1094995529
    receive_frame ret=-11
    done without crash
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
