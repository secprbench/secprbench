# Verification report: pr_review_REPORT-200e0cba677b0d47

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: IntegerOverflow
- **Intro commit**: `e722b443e462ba412c06ac27b3dff5686e322c9b`
- **Intro parent**: `bf1cc9a43be5d72d8aea24e927e07c7423d8298c`
- **Fix commit**: `200e0cba677b0d478576081ecf12af92b7a4a2d2`
- **Affected files**: ['libavfilter/vf_estdif.c']

## PoC
- source: agent-generated (initial source: no_poc)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/ffmpeg/1beae8510d6df459dfd7/attempts/04/pocs/ffmpeg/REPORT-200e0cba677b0d47`
- input: `None` (0 bytes)
- run.sh: False
- note: poc dir has neither run.sh nor a recognizable input file

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- Intro commit e722b443e462 newly adds libavfilter/vf_estdif.c (absent in intro_parent bf1cc9a43be5, confirmed by `ls`), including deinterlace_slice()'s slice-boundary computation `(height*jobnr)/nb_jobs` / `(height*(jobnr+1))/nb_jobs` in plain 32-bit `int` arithmetic — exactly matching meta.json's stated root cause. To get an invariant reproducer that runs identically (same command) on all three revisions without depending on the ffmpeg CLI's hard failure for an unknown filter, I built a small libavfilter API harness (/poc/poc.c) that looks up "estdif" via avfilter_get_by_name and exits cleanly (0) if it is not registered, otherwise constructs the same buffer->estdif->buffersink graph with 1500 filter threads and a 2x2000000 yuv420p frame and pulls a frame from the sink. Run via the identical build+execute command through run_poc on all three built revisions: pre_intro exits 0 and reports the filter is simply not present (expected, since the vulnerable file doesn't exist yet — there is no code path to crash); post_intro reliably reproduces a genuine AddressSanitizer heap-buffer-overflow inside deinterlace_slice() at vf_estdif.c:299 (a memcpy writing 33 bytes past the 32,000,031-byte output frame buffer allocated by filter()->ff_get_video_buffer() at vf_estdif.c:356), driven by the labelled 32-bit multiplication overflow for this height/nb_jobs combination; post_benign, which applies the fix commit's widening of the intermediate product to int64_t before dividing, runs the identical command cleanly (exit 0, output frames produced, no sanitizer report), confirming the companion patch removes the overflow-driven out-of-bounds write. The exact same command/harness was used for all three revisions, satisfying the required invariance, and pre_intro's clean pass together with post_intro's crash and post_benign's clean pass jointly confirm both introduction and the benign fix.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=bf1cc9a43be5  note=build cached
  command=bash -c 'cd /work && clang -g -O1 -fsanitize=address -fno-omit-frame-pointer -I. -o /tmp/poc /poc/poc.c libavfilter/libavfilter.a libavformat/libavformat.a libavcodec/libavcodec.a libswresample/libswresample.a libswscale/libswscale.a libpostproc/libpostproc.a libavutil/libavutil.a -pthread -lm -lz -fsanitize=address && /tmp/poc'
  poc_sha256=206c1398691c6a6804ffcf31913debcf8d161a17d52d3357e8a2578ca5c6c409
  source_integrity=True
  output_tail:
    SKIP: estdif filter not present in this build
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=e722b443e462  note=build cached
  command=bash -c 'cd /work && clang -g -O1 -fsanitize=address -fno-omit-frame-pointer -I. -o /tmp/poc /poc/poc.c libavfilter/libavfilter.a libavformat/libavformat.a libavcodec/libavcodec.a libswresample/libswresample.a libswscale/libswscale.a libpostproc/libpostproc.a libavutil/libavutil.a -pthread -lm -lz -fsanitize=address && /tmp/poc'
  poc_sha256=206c1398691c6a6804ffcf31913debcf8d161a17d52d3357e8a2578ca5c6c409
  source_integrity=True
  sanitizer:
    VERIFY_EXIT=134
    
    INFO: get_frame[0] ret=-11
    =================================================================
    ==8==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x7ff71ed32040 at pc 0x5603762eeb5a bp 0x7ff7fc083b90 sp 0x7ff7fc083360
    WRITE of size 2 at 0x7ff71ed32040 thread T1104
        #0 0x5603762eeb59 in __asan_memcpy (/tmp/poc+0x83fb59) (BuildId: a3be268cdfb47d1fef55585dfbed02d79787c476)
        #1 0x56037648d61e in deinterlace_slice /work/libavfilter/vf_estdif.c:299:13
        #2 0x5603763b515a in worker_func /work/libavfilter/pthread.c:50:15
        #3 0x5603782dbe9b in run_jobs /work/libavutil/slicethread.c:61:9
        #4 0x5603782dbe9b in thread_worker /work/libavutil/slicethread.c:85:13
        #5 0x7ffa2b617ac2 in start_thread nptl/./nptl/pthread_create.c:442:8
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=bf1cc9a43be5  note=build cached
  command=bash -c 'cd /work && clang -g -O1 -fsanitize=address -fno-omit-frame-pointer -I. -o /tmp/poc /poc/poc.c libavfilter/libavfilter.a libavformat/libavformat.a libavcodec/libavcodec.a libswresample/libswresample.a libswscale/libswscale.a libpostproc/libpostproc.a libavutil/libavutil.a -pthread -lm -lz -fsanitize=address && /tmp/poc'
  poc_sha256=206c1398691c6a6804ffcf31913debcf8d161a17d52d3357e8a2578ca5c6c409
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    OK: got output frame[1] 2x2000000
    OK: got output frame[2] 2x2000000
    OK: flush output frame[0] 2x2000000
    OK: flush output frame[1] 2x2000000
    OK: flush output frame[2] 2x2000000
    DONE
    VERIFY_EXIT=0
    
    INFO: get_frame[0] ret=-11
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
