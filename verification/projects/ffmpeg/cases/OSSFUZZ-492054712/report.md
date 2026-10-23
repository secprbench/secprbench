# Verification report: pr_review_OSSFUZZ-492054712

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: BufferOverflow
- **Intro commit**: `863c748144a1406ce6340c3eb6ce8ee52e715906`
- **Intro parent**: `3607a10dc386fc0d41372ec43f1fa98aa11b5635`
- **Fix commit**: `f84c859ec54d11bd743daafd89f42bb34873d29d`
- **Affected files**: ['libavcodec/bsf/extract_extradata.c']

## PoC
- source: agent-generated (initial source: incomplete)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/ffmpeg/b555657765217f7735ea/attempts/05/pocs/ffmpeg/OSSFUZZ-492054712`
- input: `None` (0 bytes)
- run.sh: True

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- meta.json's root cause states that write_lcevc_nalu()'s return value (an ABSOLUTE bytestream2_tell_p position in the shared PutByteContext) is misused as a per-NAL incremental size delta and summed cumulatively (*size += ret) across the NAL loop in extract_extradata_lcevc(), producing a *size far larger than the buffer that was actually allocated (extradata_size, computed correctly as a linear upper bound in the earlier dummy pass). That inflated *size later becomes 'extradata_size' in extract_extradata_filter(), which does `memset(extradata + extradata_size, 0, AV_INPUT_BUFFER_PADDING_SIZE)` — writing past the end of the av_malloc'd buffer.

Reproduction: with N=4 identical qualifying LCEVC NALs (8 bytes of real content each, matching the correct linear allocation), the corrupted cumulative size formula grows quadratically (sum of cumulative positions across iterations) while the allocation stays linear, guaranteeing the reported size exceeds the allocated capacity by a wide margin for N>=2, and I used N=4 for a comfortable margin.

- pre_intro (parent 3607a10dc386): builds fine; running the exact PoC against the built target completes without any crash — 'PoC completed without crash', av_bsf_receive_packet ultimately returns -11 (EAGAIN), no ASan report.
- post_intro (863c748144a1): the identical PoC reliably crashes: 'AddressSanitizer: heap-buffer-overflow ... WRITE of size 64', stack trace #0 __asan_memset, #1 extract_extradata_filter /work/libavcodec/bsf/extract_extradata.c:603 (the memset padding line), with the overflowing buffer allocated at extract_extradata_lcevc.c:404 (the av_malloc(extradata_size+...) line) — exactly the function/lines named in the root cause and the fix commit (f84c859ec54d, 'Replace incorrect size accounting').
- post_benign (fix applied on top of intro): identical PoC again completes cleanly with no crash, same as pre_intro ('PoC completed without crash', receive_packet -> -11).

The same reproducer command (/poc/run.sh, which compiles poc.c once with ASan and links it against each version's own built static libs, then runs it on the fixed byte input) was used unmodified across all three revisions, and the sanitizer report appears only in post_intro. This is a clean, deterministic, target-code (not reimplemented) reproduction of the exact heap-buffer-overflow described in the bug report and root cause, confirming both introduction and the benign fix.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=3607a10dc386  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=61f33efd3932d00fea7245297bad9dff8163a5e7c01edbda7efc4adc91162d03
  source_integrity=True
  output_tail:
    VERIFY_EXIT=0
    
    av_bsf_send_packet -> 0
    got packet size=32
    av_bsf_receive_packet -> -11 (final)
    PoC completed without crash
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=863c748144a1  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=61f33efd3932d00fea7245297bad9dff8163a5e7c01edbda7efc4adc91162d03
  source_integrity=True
  sanitizer:
    VERIFY_EXIT=134
    
    av_bsf_send_packet -> 0
    =================================================================
    ==12==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x609000000110 at pc 0x562837e9a94c bp 0x7ffe13f19f30 sp 0x7ffe13f19700
    WRITE of size 64 at 0x609000000110 thread T0
        #0 0x562837e9a94b in __asan_memset (/tmp/poc+0x4df94b) (BuildId: 4c33a1e278af2cfb840cc04e1dc0689aa286ec98)
        #1 0x562837eeb28b in extract_extradata_filter /work/libavcodec/bsf/extract_extradata.c:603:9
        #2 0x562837ed7760 in av_bsf_receive_packet /work/libavcodec/bsf.c:232:12
        #3 0x562837ed6640 in main /poc/poc.c:96:19
        #4 0x7fe8a430ed8f in __libc_start_call_main csu/../sysdeps/nptl/libc_start_call_main.h:58:16
        #5 0x7fe8a430ee3f in __libc_start_main csu/../csu/libc-start.c:392:3
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=3607a10dc386  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=61f33efd3932d00fea7245297bad9dff8163a5e7c01edbda7efc4adc91162d03
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    VERIFY_EXIT=0
    
    av_bsf_send_packet -> 0
    got packet size=32
    av_bsf_receive_packet -> -11 (final)
    PoC completed without crash
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
