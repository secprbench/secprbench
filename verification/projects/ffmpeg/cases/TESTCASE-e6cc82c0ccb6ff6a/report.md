# Verification report: pr_review_TESTCASE-e6cc82c0ccb6ff6a

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: OutOfBoundsRead
- **Intro commit**: `38aea9b0416f574757a56591b8a6f305cbc659ad`
- **Intro parent**: `8d209eb33c3ae900e913c6645603dfde435c59c1`
- **Fix commit**: `56309e476ab385881b15fe52634ba2208bb7f4ba`
- **Affected files**: ['libavfilter/vf_vif.c']

## PoC
- source: agent-generated (initial source: no_poc)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/ffmpeg/fcb45adf3005f0ecd0d8/attempts/01/pocs/ffmpeg/TESTCASE-e6cc82c0ccb6ff6a`
- input: `None` (0 bytes)
- run.sh: True

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- meta.json/discussion.md (upstream fix 56309e476ab3) describe an out-of-array access in libavfilter/vf_vif.c's boundary mirroring logic (vif_filter1d): a single conditional reflection of indices near image edges is insufficient once the image dimension is smaller than filt_w/2 (8), and the fix replaces it with avpriv_mirror() which mirrors repeatedly. I verified this directly: pre_intro (8d209eb33c3a) doesn't even contain vf_vif.c — the vif filter is added wholesale by the intro commit 38aea9b0416f, so the vulnerable code provably does not exist before introduction (confirmed via `ls libavfilter/vf_vif.c` failing and `ffmpeg -filters` omitting vif). post_intro, built from 38aea9b0416f, deterministically crashes with an ASan heap-buffer-overflow read at vf_vif.c:251 inside vif_filter1d when fed two 4x4 videos (4 < filt_w/2=8, matching the root cause exactly). post_benign, built with the fix applied, runs the identical script/command to completion with no sanitizer report, confirming the mirroring fix resolves the OOB read while keeping the filter fully functional. All three versions were exercised with the exact same run.sh, satisfying the same-command invariant; pre_intro's branch (filter absent) and post_intro/post_benign's branch (filter present, same ffmpeg invocation) together establish that the bug was introduced by 38aea9b0416f and removed by the fix/benign commit.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=8d209eb33c3a  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=62eb03dea9fa1a7717032f47543f55471c6ff48b72e3b8ed026d2f08920ab5d8
  source_integrity=True
  output_tail:
    VIF_FILTER_NOT_PRESENT
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=38aea9b0416f  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=62eb03dea9fa1a7717032f47543f55471c6ff48b72e3b8ed026d2f08920ab5d8
  source_integrity=True
  sanitizer:
    o) -> vif:main
      Stream #1:0 (rawvideo) -> vif:reference
      vif -> Stream #0:0 (wrapped_avframe)
    Press [q] to stop, [?] for help
    =================================================================
    ==11==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x607000002e70 at pc 0x55a00901902d bp 0x7ffd3c596e00 sp 0x7ffd3c596df8
    READ of size 4 at 0x607000002e70 thread T0
        #0 0x55a00901902c in vif_filter1d /work/libavfilter/vf_vif.c:251:33
        #1 0x55a008cfaa3a in worker_func /work/libavfilter/pthread.c:50:15
        #2 0x55a00ac601ad in run_jobs /work/libavutil/slicethread.c:61:9
        #3 0x55a00ac601ad in avpriv_slicethread_execute /work/libavutil/slicethread.c:188:19
        #4 0x55a008cfa931 in thread_execute /work/libavfilter/pthread.c:72:5
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=8d209eb33c3a  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=62eb03dea9fa1a7717032f47543f55471c6ff48b72e3b8ed026d2f08920ab5d8
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    uration: N/A, start: 0.000000, bitrate: N/A
      Stream #1:0: Video: rawvideo (I420 / 0x30323449), yuv420p, 4x4 [SAR 1:1 DAR 1:1], 25 tbr, 25 tbn, 25 tbc
    Stream mapping:
      Stream #0:0 (rawvideo) -> vif:main
      Stream #1:0 (rawvideo) -> vif:reference
      vif -> Stream #0:0 (wrapped_avframe)
    Press [q] to stop, [?] for help
    Output #0, null, to 'pipe:':
      Metadata:
        encoder         : Lavf58.67.100
      Stream #0:0: Video: wrapped_avframe, yuv420p(progressive), 4x4 [SAR 1:1 DAR 1:1], q=2-31, 200 kb/s, 25 fps, 25 tbn (default)
        Metadata:
          encoder         : Lavc58.123.100 wrapped_avframe
    frame=    1 fps=0.0 q=-0.0 size=N/A time=00:00:00.04 bitrate=N/A speed= 204x    
    frame=    5 fps=0.0 q=-0.0 Lsize=N/A time=00:00:00.20 bitrate=N/A speed=19.8x    
    video:3kB audio:0kB subtitle:0kB other streams:0kB global headers:0kB muxing overhead: unknown
    [Parsed_vif_0 @ 0x610000002740] VIF scale=0 average:1.000000 min:1.000000: max:1.000000
    [Parsed_vif_0 @ 0x610000002740] VIF scale=1 average:1.000000 min:1.000000: max:1.000000
    [Parsed_vif_0 @ 0x610000002740] VIF scale=2 average:1.000000 min:1.000000: max:1.000000
    [Parsed_vif_0 @ 0x610000002740] VIF scale=3 average:1.000000 min:1.000000: max:1.000000
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
