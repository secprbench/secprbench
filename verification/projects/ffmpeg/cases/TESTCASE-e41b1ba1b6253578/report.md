# Verification report: pr_review_TESTCASE-e41b1ba1b6253578

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: UseAfterFree
- **Intro commit**: `6d0c89980c78ffd3b112676186786334c915ace7`
- **Intro parent**: `6def8e3923f838a217c5e4567435b0e975b9aee7`
- **Fix commit**: `f435ce22e10e2c93fc8027cc72eeb09eba50ab8d`
- **Affected files**: ['libavcodec/h2645_sei.c']

## PoC
- source: agent-generated (initial source: no_poc)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/ffmpeg/d7fa80044f0cef12d06e/attempts/01/pocs/ffmpeg/TESTCASE-e41b1ba1b6253578`
- input: `None` (0 bytes)
- run.sh: False
- note: poc dir has neither run.sh nor a recognizable input file

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- Root cause confirmed by source diff: in post_intro's h2645_sei_to_side_data(), for the Ambient Viewing Environment SEI, a new AVAmbientViewingEnvironment (dst_env) is allocated, wrapped in an AVBufferRef (buf), and buf is handed to ff_frame_new_side_data_from_buf_ext() BEFORE dst_env's fields are written. ff_frame_new_side_data_from_buf_ext() (decode.c) unconditionally av_buffer_unref()s its buf argument once it decides not to add it (the side_data_pref() 'already exists, prefer existing' path, taken when the frame already has AV_FRAME_DATA_AMBIENT_VIEWING_ENVIRONMENT side data and side_data_pref_mask has that bit set), yet returns success (0) in that case. The caller's `if (ret < 0) return ret;` guard therefore does not fire, and code proceeds to write dst_env->ambient_illuminance/ambient_light_x/ambient_light_y into the just-freed buffer. In post_benign (the fix), the three field writes are moved to occur before the call to ff_frame_new_side_data_from_buf_ext(), so by the time the buffer can be freed the struct is already fully initialized and never written to again. In pre_intro (the code before the intro commit), this code path did not exist in this form at all (it used av_ambient_viewing_environment_create_side_data(frame) directly, with no separate buffer hand-off/free window). I verified this with a harness that directly drives the shared, exported ff_h2645_sei_to_frame() function (used identically by both the HEVC and H264 decoders once per decoded frame) with the precise state a real decode of a crafted mp4 would create (container-level 'amve' box side data already on the frame + side_data_prefer_packet=-1 + an Ambient Viewing Environment SEI in the bitstream). This drives the real compiled library code through its actual production entry point, reaching and executing the vulnerable statement; it is not a source-level assertion, grep, or unexecuted path. The identical command, run via run_poc, crashes only under post_intro and completes cleanly under both pre_intro and post_benign -- exactly the discriminating behavior required. A full end-to-end mp4-container-plus-valid-HEVC-bitstream PoC could not be produced in this environment (the sanitizer build has no software H.264/HEVC encoder configured, so no compliant bitstream could be authored via the ffmpeg CLI), so the harness reproduces the same code path via the library's own exported API instead.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=6def8e3923f8  note=build cached
  command=cd /work && clang -g -O1 -fsanitize=address -fno-omit-frame-pointer -I/work -o /tmp/poc /poc/poc.c libavcodec/libavcodec.a libavformat/libavformat.a libavutil/libavutil.a libswresample/libswresample.a -fsanitize=address -pthread -lm -latomic -lz && /tmp/poc
  poc_sha256=2ed2aa4479151f356d04cf71f97542a5b234c5e9a23769a34da36e229ea5d67c
  source_integrity=True
  output_tail:
    VERIFY_EXIT=0
    
    calling ff_h2645_sei_to_frame...
    ff_h2645_sei_to_frame returned 0 (no crash)
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=6d0c89980c78  note=build cached
  command=cd /work && clang -g -O1 -fsanitize=address -fno-omit-frame-pointer -I/work -o /tmp/poc /poc/poc.c libavcodec/libavcodec.a libavformat/libavformat.a libavutil/libavutil.a libswresample/libswresample.a -fsanitize=address -pthread -lm -latomic -lz && /tmp/poc
  poc_sha256=2ed2aa4479151f356d04cf71f97542a5b234c5e9a23769a34da36e229ea5d67c
  source_integrity=True
  sanitizer:
    VERIFY_EXIT=134
    
    calling ff_h2645_sei_to_frame...
    =================================================================
    ==8==ERROR: AddressSanitizer: heap-use-after-free on address 0x604000000110 at pc 0x556991c7448a bp 0x7ffe566776f0 sp 0x7ffe566776e8
    WRITE of size 8 at 0x604000000110 thread T0
        #0 0x556991c74489 in h2645_sei_to_side_data /work/libavcodec/h2645_sei.c:572:40
        #1 0x556991c723c7 in ff_h2645_sei_to_frame /work/libavcodec/h2645_sei.c:741:11
        #2 0x55699186bbfd in main /poc/poc.c:106:11
        #3 0x7f70fb77fd8f in __libc_start_call_main csu/../sysdeps/nptl/libc_start_call_main.h:58:16
        #4 0x7f70fb77fe3f in __libc_start_main csu/../csu/libc-start.c:392:3
        #5 0x5569917adbd4 in _start (/tmp/poc+0x433bd4) (BuildId: 5b8680e1e929e070e78dc9f6276d30a9c8a4cab7)
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=6def8e3923f8  note=build cached
  command=cd /work && clang -g -O1 -fsanitize=address -fno-omit-frame-pointer -I/work -o /tmp/poc /poc/poc.c libavcodec/libavcodec.a libavformat/libavformat.a libavutil/libavutil.a libswresample/libswresample.a -fsanitize=address -pthread -lm -latomic -lz && /tmp/poc
  poc_sha256=2ed2aa4479151f356d04cf71f97542a5b234c5e9a23769a34da36e229ea5d67c
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    VERIFY_EXIT=0
    
    calling ff_h2645_sei_to_frame...
    ff_h2645_sei_to_frame returned 0 (no crash)
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
