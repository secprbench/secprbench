# Verification report: pr_review_OSSFUZZ-391935573

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: BufferOverflow
- **Intro commit**: `63ea1660fa06d30c3bcbad68373a6caf88ac9c4c`
- **Intro parent**: `ac2442f0a7a97d41089fffe51cc831913799c89b`
- **Fix commit**: `43926e026dd80918e1387801077c58cf02b6c99d`
- **Affected files**: ['libavcodec/mmvideo.c']

## PoC
- source: agent-generated (initial source: incomplete)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/ffmpeg/17adec9a9fa40ec96aa7/attempts/01/pocs/ffmpeg/OSSFUZZ-391935573`
- input: `poc.mm` (50 bytes)
- run.sh: False

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- meta.json's root cause states that commit 63ea1660fa06 replaced mm_decode_pal's fixed 128-iteration loop with attacker-controlled 'start'/'count' values used to index s->palette[] (256-entry array) without clamping start+i to valid bounds. I built pre_intro (ac2442f0a7a9), post_intro (63ea1660fa06), and post_benign (the fix state) with sanitizers in Docker, then crafted a minimal MM-format PoC exercising exactly the MM_TYPE_PALETTE code path with start=0xFFF0, count=4, causing writes far outside the palette array. Running the identical command and input across all three builds: pre_intro exits cleanly (0) and decodes without error; post_intro crashes with AddressSanitizer SEGV (WRITE) at libavcodec/mmvideo.c:84:29 inside mm_decode_pal/mm_decode_frame, exactly the vulnerable line `s->palette[start+i] = ...`; post_benign (fixed code, which clamps/masks the index) again exits cleanly (0) with identical decode output and no crash. This establishes the bug was introduced by 63ea1660fa06 and is removed by the fix/benign companion, using the same reproducer throughout.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=ac2442f0a7a9  note=build cached
  command=/work/ffmpeg -f mm -i $INPUT -f null -
  poc_sha256=216dd3edbf955735d61711c5841e0d4523af4edc252c1d5eb549cf36c83971fe
  source_integrity=True
  output_tail:
      libswscale      8.  9.101 /  8.  9.101
      libswresample   5.  4.100 /  5.  4.100
      libpostproc    58.  4.100 / 58.  4.100
    Input #0, mm, from '/poc/poc.mm':
      Duration: N/A, start: 0.000000, bitrate: N/A
      Stream #0:0: Video: mmvideo, pal8, 64x64, 10 tbr, 10 tbn
    Stream mapping:
      Stream #0:0 -> #0:0 (mmvideo (native) -> wrapped_avframe (native))
    Press [q] to stop, [?] for help
    [in#0/mm @ 0x612000000040] Error during demuxing: Input/output error
    [vf#0:0 @ 0x614000000040] No filtered frames for output stream, trying to initialize anyway.
    Output #0, null, to 'pipe:':
      Metadata:
        encoder         : Lavf61.9.100
      Stream #0:0: Video: wrapped_avframe, pal8(progressive), 64x64, q=2-31, 200 kb/s, 10 fps, 10 tbn
        Metadata:
          encoder         : Lavc61.25.102 wrapped_avframe
    [out#0/null @ 0x611000000180] video:0KiB audio:0KiB subtitle:0KiB other streams:0KiB global headers:0KiB muxing overhead: unknown
    [out#0/null @ 0x611000000180] Output file is empty, nothing was encoded(check -ss / -t / -frames parameters if used)
    frame=    0 fps=0.0 q=0.0 Lsize=N/A time=N/A bitrate=N/A speed=N/A
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=63ea1660fa06  note=build cached
  command=/work/ffmpeg -f mm -i $INPUT -f null -
  poc_sha256=216dd3edbf955735d61711c5841e0d4523af4edc252c1d5eb549cf36c83971fe
  source_integrity=True
  sanitizer:
    0 tbr, 10 tbn
    Stream mapping:
      Stream #0:0 -> #0:0 (mmvideo (native) -> wrapped_avframe (native))
    Press [q] to stop, [?] for help
    [in#0/mm @ 0x612000000040] Error during demuxing: Input/output error
    AddressSanitizer:DEADLYSIGNAL
    =================================================================
    ==8==ERROR: AddressSanitizer: SEGV on unknown address 0x619000040a50 (pc 0x556ae1b48bfd bp 0x7fee3f7fc110 sp 0x7fee3f7fc070 T3)
    ==8==The signal is caused by a WRITE memory access.
        #0 0x556ae1b48bfd in mm_decode_pal /work/libavcodec/mmvideo.c:84:29
        #1 0x556ae1b48bfd in mm_decode_frame /work/libavcodec/mmvideo.c:205:30
        #2 0x556ae16df2e6 in decode_simple_internal /work/libavcodec/decode.c:443:16
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=ac2442f0a7a9  note=build cached
  command=/work/ffmpeg -f mm -i $INPUT -f null -
  poc_sha256=216dd3edbf955735d61711c5841e0d4523af4edc252c1d5eb549cf36c83971fe
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
      libswscale      8.  9.101 /  8.  9.101
      libswresample   5.  4.100 /  5.  4.100
      libpostproc    58.  4.100 / 58.  4.100
    Input #0, mm, from '/poc/poc.mm':
      Duration: N/A, start: 0.000000, bitrate: N/A
      Stream #0:0: Video: mmvideo, pal8, 64x64, 10 tbr, 10 tbn
    Stream mapping:
      Stream #0:0 -> #0:0 (mmvideo (native) -> wrapped_avframe (native))
    Press [q] to stop, [?] for help
    [in#0/mm @ 0x612000000040] Error during demuxing: Input/output error
    [vf#0:0 @ 0x614000000040] No filtered frames for output stream, trying to initialize anyway.
    Output #0, null, to 'pipe:':
      Metadata:
        encoder         : Lavf61.9.100
      Stream #0:0: Video: wrapped_avframe, pal8(progressive), 64x64, q=2-31, 200 kb/s, 10 fps, 10 tbn
        Metadata:
          encoder         : Lavc61.25.102 wrapped_avframe
    [out#0/null @ 0x611000000180] video:0KiB audio:0KiB subtitle:0KiB other streams:0KiB global headers:0KiB muxing overhead: unknown
    [out#0/null @ 0x611000000180] Output file is empty, nothing was encoded(check -ss / -t / -frames parameters if used)
    frame=    0 fps=0.0 q=0.0 Lsize=N/A time=N/A bitrate=N/A speed=N/A
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
