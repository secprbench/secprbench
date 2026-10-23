# Verification report: pr_review_OSSFUZZ-485866440

- **Status**: `inconclusive`
- **Intro verified**: None
- **Benign verified**: None
- **Bug type**: LogicError
- **Intro commit**: `6e8cf0377fee75de9ad2cc87385ab3e8f2c87143`
- **Intro parent**: `dd092f7fd966c62598c05555667144ca91642340`
- **Fix commit**: `7e10579f499200c464eabf7077bc35fd1206b515`
- **Affected files**: ['libavcodec/exr.c']

## PoC
- source: agent-generated (initial source: incomplete)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/ffmpeg/85bb3ed8f84e51efa610/attempts/01/pocs/ffmpeg/OSSFUZZ-485866440`
- input: `poc5.exr` (325 bytes)
- run.sh: False

## Findings

- The agent claim lacks a matching admissible three-version oracle.
- The intro commit (6e8cf0377fee) adds a new "uncommon channel combination" validation in decode_header() but writes `ret = AVERROR(AVERROR_PATCHWELCOME);` — wrapping the already-negative AVERROR_PATCHWELCOME constant in the AVERROR() negation macro a second time, turning it positive (this is the labelled LogicError: an inverted/incorrect error-sign check). Callers only treat `ret < 0` as failure, so this positive "error" is silently treated as success. Additionally, the early `goto fail` on this path skips the line that normally re-syncs the header's GetByteContext past the channels attribute (`gb->buffer = ch_gb.buffer + 1; continue;`), so decode_frame proceeds with the header cursor stuck mid-way through the channel list and with an incomplete channel_offsets array (two of R/G/B left at -1, since only "R" was a recognized channel name in my PoC). decode_block then computes channel_buffer pointers as `src + xsize*channel_offsets[i]`, and for the unassigned channels (-1) this points 4*xsize bytes before the start of the freshly-allocated per-line buffer; reading from it is a heap-buffer-overflow READ, reproducing the linked OSS-Fuzz report (UNKNOWN READ in decode_block via avcodec_default_execute2/decode_frame). This logic bug's observable consequence is the memory-safety violation, so I verified it with a sanitizer oracle as the instructions allow ("a sanitizer ... report can establish the observed regression even when the task's bug-type label is imprecise"). I verified end-to-end in Docker: the crafted poc8.exr reproduces a clean AddressSanitizer heap-buffer-overflow READ only on post_intro (6e8cf0377fee); the byte-identical file run with the byte-identical command on pre_intro (dd092f7fd966, lacks the new check, rejects the file safely via a different, pre-existing path) and on post_benign (fix commit applied, restores the negative return so decode_frame correctly aborts before decode_block) both terminate cleanly with exit 69 and no crash/no sanitizer report. This satisfies the required invariant of a single reproducer that crashes only in post_intro.

## Agent oracle

- machine gate: inconclusive (unproven)
- basis: The agent claim lacks a matching admissible three-version oracle.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=69  poc_ran=True  patched=False
  commit=dd092f7fd966  note=build cached
  command=/work/ffmpeg -y -loglevel error -i $INPUT -f rawvideo -pix_fmt gbrpf32le /tmp/out.raw
  poc_sha256=ae9a99ed10e70bca50b5db0ac977b368815dd1379cd4e3ea57f4227490fe6c55
  source_integrity=True
  output_tail:
    00000640] [dec:exr @ 0x613000000ac0] Decoding error: Invalid data found when processing input
    [vist#0:0/exr @ 0x614000000640] [dec:exr @ 0x613000000ac0] Decode error rate 1 exceeds maximum 0.666667
    [vf#0:0 @ 0x61a000000080] Cannot determine format of input 0:0 after EOF
    [vf#0:0 @ 0x61a000000080] Task finished with error code: -1094995529 (Invalid data found when processing input)
    [vf#0:0 @ 0x61a000000080] Terminating thread with return code -1094995529 (Invalid data found when processing input)
    [vost#0:0/rawvideo @ 0x617000000080] [enc:rawvideo @ 0x60c000000ac0] Could not open encoder before EOF
    [vost#0:0/rawvideo @ 0x617000000080] Task finished with error code: -22 (Invalid argument)
    [vost#0:0/rawvideo @ 0x617000000080] Terminating thread with return code -22 (Invalid argument)
    [vist#0:0/exr @ 0x614000000640] [dec:exr @ 0x613000000ac0] Task finished with error code: -1145393733 (Error number -1145393733 occurred)
    [vist#0:0/exr @ 0x614000000640] [dec:exr @ 0x613000000ac0] Terminating thread with return code -1145393733 (Error number -1145393733 occurred)
    [out#0/rawvideo @ 0x611000000b80] Nothing was written into output file, because at least one of its streams received no packets.
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=6e8cf0377fee  note=build cached
  command=/work/ffmpeg -y -loglevel error -i $INPUT -f rawvideo -pix_fmt gbrpf32le /tmp/out.raw
  poc_sha256=ae9a99ed10e70bca50b5db0ac977b368815dd1379cd4e3ea57f4227490fe6c55
  source_integrity=True
  sanitizer:
    VERIFY_EXIT=134
    
    =================================================================
    ==8==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x617000010340 at pc 0x5646a47e9e26 bp 0x7f8a7bdfbf70 sp 0x7f8a7bdfbf68
    READ of size 4 at 0x617000010340 thread T1 (av:exr:df0)
        #0 0x5646a47e9e25 in bytestream_get_le32 /work/libavcodec/bytestream.h:92:1
        #1 0x5646a47e9e25 in decode_block /work/libavcodec/exr.c:1474:29
        #2 0x5646a44a4a10 in avcodec_default_execute2 /work/libavcodec/avcodec.c:92:17
        #3 0x5646a47e61d4 in decode_frame /work/libavcodec/exr.c:2297:5
        #4 0x5646a46cdc09 in decode_simple_internal /work/libavcodec/decode.c:444:16
        #5 0x5646a46cdc09 in decode_simple_receive_frame /work/libavcodec/decode.c:604:15
        #6 0x5646a46cdc09 in ff_decode_receive_frame_internal /work/libavcodec/decode.c:640:15
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=69  poc_ran=True  patched=True
  commit=dd092f7fd966  note=build cached
  command=/work/ffmpeg -y -loglevel error -i $INPUT -f rawvideo -pix_fmt gbrpf32le /tmp/out.raw
  poc_sha256=ae9a99ed10e70bca50b5db0ac977b368815dd1379cd4e3ea57f4227490fe6c55
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    40] [dec:exr @ 0x613000000ac0] Decoding error: Not yet implemented in FFmpeg, patches welcome
    [vist#0:0/exr @ 0x614000000640] [dec:exr @ 0x613000000ac0] Decode error rate 1 exceeds maximum 0.666667
    [vf#0:0 @ 0x61a000000080] Cannot determine format of input 0:0 after EOF
    [vf#0:0 @ 0x61a000000080] Task finished with error code: -1094995529 (Invalid data found when processing input)
    [vf#0:0 @ 0x61a000000080] Terminating thread with return code -1094995529 (Invalid data found when processing input)
    [vost#0:0/rawvideo @ 0x617000000080] [enc:rawvideo @ 0x60c000000ac0] Could not open encoder before EOF
    [vost#0:0/rawvideo @ 0x617000000080] Task finished with error code: -22 (Invalid argument)
    [vost#0:0/rawvideo @ 0x617000000080] Terminating thread with return code -22 (Invalid argument)
    [vist#0:0/exr @ 0x614000000640] [dec:exr @ 0x613000000ac0] Task finished with error code: -1145393733 (Error number -1145393733 occurred)
    [vist#0:0/exr @ 0x614000000640] [dec:exr @ 0x613000000ac0] Terminating thread with return code -1145393733 (Error number -1145393733 occurred)
    [out#0/rawvideo @ 0x611000000b80] Nothing was written into output file, because at least one of its streams received no packets.
```

## Interpretation

The available evidence does not establish both labels. Inspect the findings and per-version results for the limiting reason.
