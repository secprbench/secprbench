# Verification report: pr_review_REPORT-c911e0001115bbda

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: OutOfBoundsRead
- **Intro commit**: `cc85ca1cb347570a95d8615b7d4c7b542042b7f0`
- **Intro parent**: `2fc309e699ebb65834509194df806e4e3e1621a8`
- **Fix commit**: `c911e0001115bbda904ad103b12c27b9a3c0c265`
- **Affected files**: ['libavcodec/exr.c']

## PoC
- source: agent-generated (initial source: no_poc)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/ffmpeg/d4965eff5d34c5bfc2c8/attempts/03/pocs/ffmpeg/REPORT-c911e0001115bbda`
- input: `poc.exr` (517 bytes)
- run.sh: True

## Findings

- Exact bug and unaffected output lines matched the shared three-version Docker replay.
- meta.json's root cause is exactly reproduced end-to-end. dwa_uncompress() computes `dc_w = td->xsize >> 3` / `dc_h = td->ysize >> 3` (floor) in the intro commit (cc85ca1c), and `dc_w = (td->xsize+7)>>3` / `dc_h = (td->ysize+7)>>3` (ceil) in the fix commit (c911e0001115). The per-block DC index `idx = (x>>3) + (y>>3)*dc_w + dc_w*dc_h*j` is used only to READ `dc[idx]`; for a non-8-aligned dimension the outer x/y loop still visits `ceil(size/8)` blocks, so with the buggy floor-based dc_w/dc_h the last block's read aliases onto a different (smaller) index than the one a correctly-sized/encoded buffer intends for it -- i.e. it reads outside the intended per-block sub-region of the shared dc_data array. I verified mathematically (idx_buggy(x,y,j) <= idx_fixed(x,y,j) pointwise for every position, since dc_w_buggy<=dc_w_fixed and dc_h_buggy<=dc_h_fixed always) and confirmed empirically that this specific mismatch is always contained within the DWA thread buffer's generous allocation (av_fast_padded_malloc adds ~2x + rounding + 64-byte headroom), so for any dc_count consistent with the image geometry this manifests as a silent wrong-slot READ rather than an ASan-detectable heap overflow; a deliberately tiny/inconsistent dc_count (e.g. dc_count=0) does crash under ASan, but it crashes BOTH post_intro and post_benign identically (confirmed empirically), so it is not diagnostic of this specific fix and was not used as evidence. Instead I built a precise behavioral oracle isolating the exact aliased slot. Results, identical command/input across all three builds: pre_intro fails to decode at all (\"Compression 8 is not implemented ... patches welcome\") because DWA decoding did not exist before the intro commit, so the flaw cannot manifest there (intro_verified=yes: the bug is reachable only starting at the intro commit, which is the commit that introduces DWA decoding with the floor-division bug baked in from the start). post_intro decodes and prints PIXEL_G=PIXEL_B=PIXEL_R=0.9999998807907104, exactly matching to_linear(half(8.0)/8)=to_linear(1.0)=1.0 -- i.e. it read the WRONG DC slot (20) that the floor formula aliases the last block onto. post_benign decodes (with the fix's own added avpriv_request_sample \"odd dimensions DWA\" notice) and prints PIXEL_G=PIXEL_B=PIXEL_R=4876797.5, matching to_linear(half(64.0)/8)=to_linear(8.0)=exp(2.2)^7≈4,876,797 -- i.e. it read the CORRECT DC slot (23) that the ceiling formula assigns to that block. The observed post_intro value is wrong by six orders of magnitude and traces precisely to the labeled off-by-rounding root cause; pre_intro and post_benign both complete without exhibiting it (pre_intro because the feature is absent; post_benign because it reads the correct slot).

## Agent oracle

- machine gate: verified (behavioral)
- basis: Exact bug and unaffected output lines matched the shared three-version Docker replay.
- bug_marker: "PIXEL_G=0.9999998807907104 PIXEL_B=0.9999998807907104 PIXEL_R=0.9999998807907104"
- pre_marker: "[exr @ 0x619000002380] Compression 8 is not implemented. Update your FFmpeg version to the newest one from Git. If the problem still occurs, it means that your file has a feature which has not been implemented."
- benign_marker: "PIXEL_G=4876797.5 PIXEL_B=4876797.5 PIXEL_R=4876797.5"
- target execution: post_intro run_poc OUTPUT TAIL ends with: 'PIXEL_G=0.9999998807907104 PIXEL_B=0.9999998807907104 PIXEL_R=0.9999998807907104'. post_benign run_poc OUTPUT TAIL includes the fix's own diagnostic '[exr @ ...] odd dimensions DWA is not implemented. Update your FFmpeg version...' (from the newly-added avpriv_request_sample call in the fix commit) followed by 'PIXEL_G=4876797.5 PIXEL_B=4876797.5 PIXEL_R=4876797.5'. pre_intro run_poc OUTPUT TAIL shows decode failure: 'Compression 8 is not implemented ... Error while decoding stream #0:0: Not yet implemented in FFmpeg, patches welcome', with no pixel output (insufficient_output_bytes=0).

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=2fc309e699eb  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=1243771cff3195f50b8c64d3462efff3e9dbc037b99c87e6b13ae1468000e992
  source_integrity=True
  output_tail:
      Stream #0:0 -> #0:0 (exr (native) -> rawvideo (native))
    Press [q] to stop, [?] for help
    [exr @ 0x619000002380] Compression 8 is not implemented. Update your FFmpeg version to the newest one from Git. If the problem still occurs, it means that your file has a feature which has not been implemented.
    Error while decoding stream #0:0: Not yet implemented in FFmpeg, patches welcome
    [buffer @ 0x60c0000004c0] Unable to parse option value "0x0" as image size
        Last message repeated 1 times
    [buffer @ 0x60c0000004c0] Error setting option video_size to value 0x0.
    [graph 0 input from stream 0:0 @ 0x610000000140] Error applying options to the filter.
    Error reinitializing filters!
    Error while filtering: Invalid argument
    Finishing stream 0:0 without any data written to it.
    [buffer @ 0x60c000000580] Unable to parse option value "0x0" as image size
        Last message repeated 1 times
    [buffer @ 0x60c000000580] Error setting option video_size to value 0x0.
    [graph 0 input from stream 0:0 @ 0x610000000340] Error applying options to the filter.
    Error configuring filter graph
    Conversion failed!
    PIXEL_READ_FAILED insufficient_output_bytes=0
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=cc85ca1cb347  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=1243771cff3195f50b8c64d3462efff3e9dbc037b99c87e6b13ae1468000e992
  source_integrity=True
  output_tail:
      libswresample   3.  8.100 /  3.  8.100
      libpostproc    55.  8.100 / 55.  8.100
    Input #0, exr_pipe, from '/poc/poc.exr':
      Duration: N/A, bitrate: N/A
      Stream #0:0: Video: exr, gbrpf32le, 42x30 [SAR 1:1 DAR 7:5], 25 fps, 25 tbr, 25 tbn, 25 tbc
    Stream mapping:
      Stream #0:0 -> #0:0 (exr (native) -> rawvideo (native))
    Press [q] to stop, [?] for help
    Output #0, rawvideo, to '/tmp/verify_out.raw':
      Metadata:
        encoder         : Lavf58.69.100
      Stream #0:0: Video: rawvideo, gbrpf32le(progressive), 42x30 [SAR 1:1 DAR 7:5], q=2-31, 3024 kb/s, 25 fps, 25 tbn
        Metadata:
          encoder         : Lavc58.128.100 rawvideo
    frame=    1 fps=0.0 q=-0.0 size=      15kB time=00:00:00.04 bitrate=3024.0kbits/s speed= 952x    
    frame=    1 fps=0.0 q=-0.0 Lsize=      15kB time=00:00:00.04 bitrate=3024.0kbits/s speed=4.49x    
    video:15kB audio:0kB subtitle:0kB other streams:0kB global headers:0kB muxing overhead: 0.000000%
    PIXEL_G=0.9999998807907104 PIXEL_B=0.9999998807907104 PIXEL_R=0.9999998807907104
    VERIFY_EXIT=0
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=2fc309e699eb  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=1243771cff3195f50b8c64d3462efff3e9dbc037b99c87e6b13ae1468000e992
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    le, 42x30 [SAR 1:1 DAR 7:5], 25 fps, 25 tbr, 25 tbn, 25 tbc
    Stream mapping:
      Stream #0:0 -> #0:0 (exr (native) -> rawvideo (native))
    Press [q] to stop, [?] for help
    [exr @ 0x619000002880] odd dimensions DWA is not implemented. Update your FFmpeg version to the newest one from Git. If the problem still occurs, it means that your file has a feature which has not been implemented.
    [exr @ 0x619000002880] If you want to help, upload a sample of this file to https://streams.videolan.org/upload/ and contact the ffmpeg-devel mailing list. (ffmpeg-devel@ffmpeg.org)
    Output #0, rawvideo, to '/tmp/verify_out.raw':
      Metadata:
        encoder         : Lavf58.69.100
      Stream #0:0: Video: rawvideo, gbrpf32le(progressive), 42x30 [SAR 1:1 DAR 7:5], q=2-31, 3024 kb/s, 25 fps, 25 tbn
        Metadata:
          encoder         : Lavc58.128.100 rawvideo
    frame=    1 fps=0.0 q=-0.0 size=      15kB time=00:00:00.04 bitrate=3024.0kbits/s speed= 541x    
    frame=    1 fps=0.0 q=-0.0 Lsize=      15kB time=00:00:00.04 bitrate=3024.0kbits/s speed=3.65x    
    video:15kB audio:0kB subtitle:0kB other streams:0kB global headers:0kB muxing overhead: 0.000000%
    PIXEL_G=4876797.5 PIXEL_B=4876797.5 PIXEL_R=4876797.5
    VERIFY_EXIT=0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
