# Verification report: pr_review_OSSFUZZ-490576036

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: IntegerOverflow
- **Intro commit**: `3dba9eb80663abf77b083878a2f6e0f77abf81a7`
- **Intro parent**: `4e32fb4c2abaee9f71cf1d67d306dd5486fbad23`
- **Fix commit**: `248b481c337d917e0fece9555ae59b5375c725c6`
- **Affected files**: ['libavcodec/bsf/extract_extradata.c']

## PoC
- source: agent-generated (initial source: incomplete)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/ffmpeg/310e7301bc224dca25f0/attempts/05/pocs/ffmpeg/OSSFUZZ-490576036`
- input: `poc.bin` (1159 bytes)
- run.sh: True

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- Root cause matches meta.json exactly: in write_lcevc_nalu() (libavcodec/bsf/extract_extradata.c), `payload_size` is declared `int` but assigned from get_mb() which returns `uint64_t`; a crafted multi-byte value truncates to a negative int, making `block_size = payload_size + offset` negative. The check `if (block_size >= bytestream2_get_bytes_left(&gbc)) return AVERROR_INVALIDDATA;` is then bypassed (negative < any non-negative bytes-left). The subsequent bytestream2_put_buffer() call's destination-capacity clamp (drawn from the shared, multi-NAL combined extradata buffer, which has slack because an earlier NAL's blocks were legitimately skipped/uncopied) exceeds the bytes actually available in the malformed NAL's own source buffer, causing memcpy to read past the end of the heap allocation.

Reproduction: identical PoC + identical run.sh-driven command across all three builds.
- pre_intro (4e32fb4c2aba): LCEVC support / write_lcevc_nalu does not exist yet (codec_ids array has no AV_CODEC_ID_LCEVC entry); the input's codec-select byte instead maps to a different codec via the smaller table, and the run completes cleanly (DONE_NO_CRASH, exit 0). Confirms the bug is not present pre-introduction.
- post_intro (3dba9eb80663): AddressSanitizer reports "heap-buffer-overflow READ of size 115" 0 bytes past a 191-byte heap region, with the crashing stack exactly write_lcevc_nalu -> extract_extradata_lcevc -> extract_extradata_filter -> av_bsf_receive_packet, matching the oss-fuzz report's "Crash Type: Heap-buffer-overflow READ" and "Crash State: write_lcevc_nalu / extract_extradata_lcevc / extract_extradata_filter" verbatim.
- post_benign (fix 248b481c337d applied on top of the LCEVC feature, verified by reading the source: payload_size is now uint64_t and a `payload_size > INT_MAX - offset` check rejects the crafted value before it can produce a negative block_size): the same input completes cleanly (DONE_NO_CRASH, exit 0). I verified via source inspection that the intended fix diff (typed as uint64_t + INT_MAX bound check) is present in this build, and confirmed no crash with the exact reproducer.

Note: an initial 2-NAL variant of this PoC (malformed NAL placed last) caused a *different*, unrelated crash in post_benign (a SEGV in extract_extradata_filter's memset, due to a separate, pre-existing/adjacent defect where extract_extradata_lcevc's loop assigns `*size = write_lcevc_nalu(...)` without checking for a negative AVERROR return). That was not the labelled bug, so I revised the PoC to include a trailing well-formed 3rd NAL, which causes the loop's final `*size` assignment to come from a successful call, correctly isolating the test to only the intro'd integer-overflow bug and confirming benign truly fixes it without being confounded by that adjacent issue.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=4e32fb4c2aba  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=daa595bf628715e6f87c1d0ccd31639c67ece79d93a612759d917aefd8a5fa01
  source_integrity=True
  output_tail:
    DONE_NO_CRASH
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=3dba9eb80663  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=daa595bf628715e6f87c1d0ccd31639c67ece79d93a612759d917aefd8a5fa01
  source_integrity=True
  sanitizer:
    VERIFY_EXIT=134
    
    =================================================================
    ==14==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x6100000000ff at pc 0x55a917d2c527 bp 0x7ffc73831790 sp 0x7ffc73830f60
    READ of size 115 at 0x6100000000ff thread T0
        #0 0x55a917d2c526 in __asan_memcpy (/tmp/bsf_fuzzer+0x4d9526) (BuildId: 036641239ee40305226319b3d49871544441d2ee)
        #1 0x55a917d6fd1b in bytestream2_put_buffer /work/./libavcodec/bytestream.h:296:5
        #2 0x55a917d6fd1b in write_lcevc_nalu /work/libavcodec/bsf/extract_extradata.c:343:13
        #3 0x55a917d6ec75 in extract_extradata_lcevc /work/libavcodec/bsf/extract_extradata.c
        #4 0x55a917d6c38a in extract_extradata_filter /work/libavcodec/bsf/extract_extradata.c:588:11
        #5 0x55a917d6a190 in av_bsf_receive_packet /work/libavcodec/bsf.c:232:12
        #6 0x55a917d68c2e in LLVMFuzzerTestOneInput /work/tools/target_bsf_fuzzer.c:155:16
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=4e32fb4c2aba  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=daa595bf628715e6f87c1d0ccd31639c67ece79d93a612759d917aefd8a5fa01
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    DONE_NO_CRASH
    VERIFY_EXIT=0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
