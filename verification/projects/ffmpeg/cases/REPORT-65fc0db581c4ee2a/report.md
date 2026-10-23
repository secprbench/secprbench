# Verification report: pr_review_REPORT-65fc0db581c4ee2a

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: LogicError
- **Intro commit**: `425c3234206c042273e001c8865391a53ce5855e`
- **Intro parent**: `de976eaf30df33e86c58c8c9af9905c1d8441934`
- **Fix commit**: `65fc0db581c4ee2a891b7b72f6056357ceb3b0bd`
- **Affected files**: ['libavformat/hlsenc.c']

## PoC
- source: agent-generated (initial source: no_poc)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/ffmpeg/889f7e3ff5d69416e7e6/attempts/04/pocs/ffmpeg/REPORT-65fc0db581c4ee2a`
- input: `sub.srt` (89 bytes)
- run.sh: True

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- meta.json/discussion.md describe a format-string vulnerability introduced in libavformat/hlsenc.c's parse_playlist(), where the VTT basename (derived from the user-supplied output filename/template) is passed directly as the fmt argument to snprintf() instead of being treated as opaque data. Code inspection confirmed: pre_intro (de976eaf30df) has no vtt-handling code at all in parse_playlist (the has_subtitle branch does not exist there). post_intro (425c3234206c) adds exactly the vulnerable line `snprintf(vtt_file, len, vtt_basename, vtt_index);` at hlsenc.c:1324, where vtt_basename = av_basename(vs->vtt_basename) and vs->vtt_basename is built from vs->m3u8_name (derived from the output path given on the command line) concatenated with "%d.vtt"/".vtt". post_benign (the fix, mechanically composed) replaces this with `replace_int_data_in_filename(&vtt_file, vtt_basename, 'd', vtt_index)`, a controlled substitution that never treats the basename as a printf-style format string. I built all three revisions with ASan and ran the identical two-pass ffmpeg HLS+webvtt reproduction command via run_poc (output path crafted with several "%s" placeholders; -hls_flags append_list on the exec'd second pass makes parse_playlist() re-parse the just-written playlist and reach the vtt branch). run_poc reported post_intro: exit=134, crashed=True, with a clear AddressSanitizer "unknown-crash" / wild-pointer READ report inside printf_common <- __interceptor_snprintf <- parse_playlist (hlsenc.c:1324:21) <- hls_init (hlsenc.c:3155:13) <- init_muxer/avformat_write_header -- exactly the labelled bug's location and mechanism. run_poc reported pre_intro: exit=0, crashed=False, and post_benign: exit=0, crashed=False, both completing the full two-pass sequence and writing output files normally, with the byte-identical command/PoC. This satisfies the required invariance and directly reproduces introduction and the companion fix's removal of the defect. (The task's "LogicError" label is imprecise; per the ground rules, the sanitizer report establishes the observed regression regardless of the label, so bug_class is recorded as memory-safety to match the actual, directly-reproduced defect.)

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=de976eaf30df  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=479f02dedfaff5c1acf18efc58359684dbfd42ca552b6e168abb146cf640f32a
  source_integrity=True
  output_tail:
      Stream #1:0 -> #0:1 (subrip (srt) -> webvtt (native))
    Press [q] to stop, [?] for help
    [mpeg4 @ 0x618000002480] too many threads/slices (16), reducing to 15
    [hls @ 0x616000000980] Opening 'out%s%s%s%s%s%s%s%s1.vtt' for writing
    Output #0, hls, to 'out%s%s%s%s%s%s%s%s.m3u8':
      Metadata:
        encoder         : Lavf61.9.100
      Stream #0:0: Video: mpeg4, yuv420p(tv, progressive), 320x240 [SAR 1:1 DAR 4:3], q=2-31, 200 kb/s, 1 fps, 90k tbn
        Metadata:
          encoder         : Lavc61.22.100 mpeg4
        Side data:
          cpb: bitrate max/min/avg: 0/0/200000 buffer size: 0 vbv_delay: N/A
      Stream #0:1: Subtitle: webvtt
        Metadata:
          encoder         : Lavc61.22.100 webvtt
    [hls @ 0x616000000980] Opening 'out%s%s%s%s%s%s%s%s1.ts' for writing
    [hls @ 0x616000000980] Opening 'out%s%s%s%s%s%s%s%s.m3u8.tmp' for writing
    [hls @ 0x616000000980] Opening 'out%s%s%s%s%s%s%s%s_vtt.m3u8.tmp' for writing
    [out#0/hls @ 0x611000001a80] video:1KiB audio:0KiB subtitle:0KiB other streams:0KiB global headers:0KiB muxing overhead: unknown
    frame=    3 fps=0.0 q=2.0 Lsize=N/A time=00:00:02.00 bitrate=N/A speed= 116x
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=425c3234206c  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=479f02dedfaff5c1acf18efc58359684dbfd42ca552b6e168abb146cf640f32a
  source_integrity=True
  sanitizer:
     (srt) -> webvtt (native))
    Press [q] to stop, [?] for help
    [mpeg4 @ 0x618000002480] too many threads/slices (16), reducing to 15
    =================================================================
    ==8==ERROR: AddressSanitizer: unknown-crash on address 0x7f07ccf2bb40 at pc 0x55e273b09a2d bp 0x7f07c2be9470 sp 0x7f07c2be8bf8
    READ of size 7 at 0x7f07ccf2bb40 thread T18 (vf#0:0)
        #0 0x55e273b09a2c in printf_common(void*, char const*, __va_list_tag*) asan_interceptors.cpp.o
        #1 0x55e273b0b350 in __interceptor_snprintf (/work/ffmpeg+0x8d7350) (BuildId: 6c67c410ea65724be6ff0e152e159228655342f5)
        #2 0x55e2743c7683 in parse_playlist /work/libavformat/hlsenc.c:1324:21
        #3 0x55e2743c7683 in hls_init /work/libavformat/hlsenc.c:3155:13
        #4 0x55e27451586e in init_muxer /work/libavformat/mux.c:388:20
        #5 0x55e27451586e in avformat_init_output /work/libavformat/mux.c:471:16
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=de976eaf30df  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=479f02dedfaff5c1acf18efc58359684dbfd42ca552b6e168abb146cf640f32a
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
      Stream #1:0 -> #0:1 (subrip (srt) -> webvtt (native))
    Press [q] to stop, [?] for help
    [mpeg4 @ 0x618000002480] too many threads/slices (16), reducing to 15
    [hls @ 0x616000000980] Opening 'out%s%s%s%s%s%s%s%s1.vtt' for writing
    Output #0, hls, to 'out%s%s%s%s%s%s%s%s.m3u8':
      Metadata:
        encoder         : Lavf61.9.100
      Stream #0:0: Video: mpeg4, yuv420p(tv, progressive), 320x240 [SAR 1:1 DAR 4:3], q=2-31, 200 kb/s, 1 fps, 90k tbn
        Metadata:
          encoder         : Lavc61.22.100 mpeg4
        Side data:
          cpb: bitrate max/min/avg: 0/0/200000 buffer size: 0 vbv_delay: N/A
      Stream #0:1: Subtitle: webvtt
        Metadata:
          encoder         : Lavc61.22.100 webvtt
    [hls @ 0x616000000980] Opening 'out%s%s%s%s%s%s%s%s1.ts' for writing
    [hls @ 0x616000000980] Opening 'out%s%s%s%s%s%s%s%s.m3u8.tmp' for writing
    [hls @ 0x616000000980] Opening 'out%s%s%s%s%s%s%s%s_vtt.m3u8.tmp' for writing
    [out#0/hls @ 0x611000001a80] video:1KiB audio:0KiB subtitle:0KiB other streams:0KiB global headers:0KiB muxing overhead: unknown
    frame=    3 fps=0.0 q=2.0 Lsize=N/A time=00:00:02.00 bitrate=N/A speed= 128x
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
