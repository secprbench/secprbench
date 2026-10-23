# Verification report: pr_review_OSSFUZZ-391962476

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: IntegerOverflow
- **Intro commit**: `86dd15fd0dd0deeb69ffcff9952b801bbb2f38c7`
- **Intro parent**: `f651ca3a6838be90e7d5189d831c9db8cb7e3ec8`
- **Fix commit**: `251d43aef0df9262f2688c1c848af993bbb67d08`
- **Affected files**: ['libavformat/mlvdec.c']

## PoC
- source: agent-generated (initial source: incomplete)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/ffmpeg/e46595354365cb012a65/attempts/03/pocs/ffmpeg/OSSFUZZ-391962476`
- input: `poc.mlv` (264 bytes)
- run.sh: False

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- Ran the identical command (`/work/ffmpeg -y -f mlv -i /poc/poc.mlv -c copy -f null -`) against all three built revisions using the same crafted MLV file. post_intro (86dd15fd0dd0) crashed with AddressSanitizer heap-buffer-overflow WRITE of size 2 at bytestream2_put_le16 <- write_tiff_short <- get_packet_lj92 <- read_packet <- ff_read_packet — matching the oss-fuzz Crash State/Type exactly. pre_intro (f651ca3a6838) lacks the LJ92/get_packet_lj92 code path entirely (the whole TIFF/LJ92 decode feature, including get_packet_lj92, was added by the intro commit), so the same input/command now completes cleanly with exit 0 and no sanitizer report -- confirming the flaw did not exist before introduction. post_benign (companion fix, added `if (size < 8) ...` and `if (size < space + 4LL) return AVERROR_INVALIDDATA;` bounds checks in read_packet()) also completes cleanly with exit 0 on the identical input: the malformed space/size relationship is now rejected via a normal recoverable AVERROR_INVALIDDATA before the underflow can occur, instead of crashing. The single reproducer/command thus cleanly discriminates all three revisions: crash only in post_intro, clean exit 0 in both pre_intro and post_benign.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=f651ca3a6838  note=build cached
  command=/work/ffmpeg -y -f mlv -i /poc/poc.mlv -c copy -f null -
  poc_sha256=d160df5e9c0e373fe8d4ab449642bb56106772ee203c670295dc5b697d0dd4fb
  source_integrity=True
  output_tail:
    nt to help, upload a sample of this file to https://streams.videolan.org/upload/ and contact the ffmpeg-devel mailing list. (ffmpeg-devel@ffmpeg.org)
    [mlv @ 0x616000000080] Opening '/poc/poc.m00' for reading
    [mlv @ 0x616000000080] Could not find codec parameters for stream 0 (Video: none (BIT[16] / 0x10544942), bayer_rggb16le, 16x16): unknown codec
    Consider increasing the value for the 'analyzeduration' (0) and 'probesize' (5000000) options
    Input #0, mlv, from '/poc/poc.mlv':
      Metadata:
        guid            : 0x0
      Duration: 00:00:00.03, bitrate: 63 kb/s
      Stream #0:0: Video: none (BIT[16] / 0x10544942), bayer_rggb16le, 16x16, 30 tbr, 30 tbn
    Stream mapping:
      Stream #0:0 -> #0:0 (copy)
    Output #0, null, to 'pipe:':
      Metadata:
        guid            : 0x0
        encoder         : Lavf61.9.105
      Stream #0:0: Video: none (BIT[16] / 0x10544942), bayer_rggb16le, 16x16, q=2-31, 30 tbr, 30 tbn
    Press [q] to stop, [?] for help
    [out#0/null @ 0x611000000180] video:0KiB audio:0KiB subtitle:0KiB other streams:0KiB global headers:0KiB muxing overhead: unknown
    [out#0/null @ 0x611000000180] Output file is empty, nothing was encoded
    frame=    0 fps=0.0 q=-1.0 Lsize=N/A time=N/A bitrate=N/A speed=N/A
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=86dd15fd0dd0  note=build cached
  command=/work/ffmpeg -y -f mlv -i /poc/poc.mlv -c copy -f null -
  poc_sha256=d160df5e9c0e373fe8d4ab449642bb56106772ee203c670295dc5b697d0dd4fb
  source_integrity=True
  sanitizer:
    mple   5.  4.100 /  5.  4.100
      libpostproc    58.  4.100 / 58.  4.100
    [mlv @ 0x616000000080] Opening '/poc/poc.m00' for reading
    =================================================================
    ==8==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x607000000068 at pc 0x5640da2f3cbc bp 0x7ffd0c6a0a50 sp 0x7ffd0c6a0a48
    WRITE of size 2 at 0x607000000068 thread T0
        #0 0x5640da2f3cbb in bytestream2_put_le16 /work/./libavcodec/bytestream.h:94:1
        #1 0x5640da2f3cbb in write_tiff_short /work/libavformat/mlvdec.c:425:5
        #2 0x5640da2f3cbb in get_packet_lj92 /work/libavformat/mlvdec.c:483:5
        #3 0x5640da2efe88 in read_packet /work/libavformat/mlvdec.c:569:19
        #4 0x5640da1d464f in ff_read_packet /work/libavformat/demux.c:649:15
        #5 0x5640da1d632a in read_frame_internal /work/libavformat/demux.c:1344:15
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=f651ca3a6838  note=build cached
  command=/work/ffmpeg -y -f mlv -i /poc/poc.mlv -c copy -f null -
  poc_sha256=d160df5e9c0e373fe8d4ab449642bb56106772ee203c670295dc5b697d0dd4fb
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
      libswresample   5.  4.100 /  5.  4.100
      libpostproc    58.  4.100 / 58.  4.100
    [mlv @ 0x616000000080] Opening '/poc/poc.m00' for reading
    Input #0, mlv, from '/poc/poc.mlv':
      Metadata:
        guid            : 0x0
      Duration: 00:00:00.03, bitrate: 63 kb/s
      Stream #0:0: Video: tiff (BIT[16] / 0x10544942), bayer_rggb16le, 16x16, 30 tbr, 30 tbn
    Stream mapping:
      Stream #0:0 -> #0:0 (copy)
    Output #0, null, to 'pipe:':
      Metadata:
        guid            : 0x0
        encoder         : Lavf61.9.105
      Stream #0:0: Video: tiff (BIT[16] / 0x10544942), bayer_rggb16le, 16x16, q=2-31, 30 tbr, 30 tbn
    Press [q] to stop, [?] for help
    [in#0/mlv @ 0x612000000040] Error during demuxing: Invalid data found when processing input
    [out#0/null @ 0x611000000180] video:0KiB audio:0KiB subtitle:0KiB other streams:0KiB global headers:0KiB muxing overhead: unknown
    [out#0/null @ 0x611000000180] Output file is empty, nothing was encoded
    frame=    0 fps=0.0 q=-1.0 Lsize=N/A time=N/A bitrate=N/A speed=N/A
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
