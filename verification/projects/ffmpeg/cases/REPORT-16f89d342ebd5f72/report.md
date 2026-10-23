# Verification report: pr_review_REPORT-16f89d342ebd5f72

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: BufferOverflow
- **Intro commit**: `536475ea058245e71f5c2e7f3d5c39b0cad465e5`
- **Intro parent**: `3b1214a89767ccd4ccdf0561952c79566cbc5b7d`
- **Fix commit**: `16f89d342ebd5f726a5787e2e00069f339c7b446`
- **Affected files**: ['libavformat/mpegts.c']

## PoC
- source: agent-generated (initial source: no_poc)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/ffmpeg/cd586f89f95e5f9fc95e/attempts/01/pocs/ffmpeg/REPORT-16f89d342ebd5f72`
- input: `poc.ts` (564 bytes)
- run.sh: False

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- Source inspection: pre_intro's new_pes_packet() in libavformat/mpegts.c has no JPEG-XS/'jxes' handling at all (grep found zero hits). post_intro (536475ea0582) adds: `if (pes->stream_id==0xbd && pes->stream_type==0x32 && pkt->size>=8 && memcmp(pkt->data+4,"jxes",4)==0) { uint32_t header_size = AV_RB32(pkt->data); pkt->data += header_size; pkt->size -= header_size; } memset(pkt->data + pkt->size, 0, AV_INPUT_BUFFER_PADDING_SIZE);` with no validation of header_size against pkt->size - exactly the labelled root cause (unchecked attacker-controlled length field used in pointer arithmetic that feeds a memset destination). post_benign adds the bounds check from the real fix: `if (header_size > pkt->size) { av_log(...); pes->flags |= AV_PKT_FLAG_CORRUPT; return AVERROR_INVALIDDATA; }` before the pointer adjustment/memset.

Reproduction: running the harness (single av_read_frame call) on poc.ts:
- pre_intro: av_read_frame returns 0, packet size=8, no crash (feature doesn't exist yet).
- post_intro: AddressSanitizer reports SEGV (wild-pointer WRITE) directly at libavformat/mpegts.c:1042 inside new_pes_packet, called via mpegts_push_data:1431 -> handle_packet -> handle_packets -> mpegts_read_packet -> ff_read_packet -> av_read_frame -> main. This is the memset writing through the pointer corrupted by `pkt->data += 0xFFFFFF00`, i.e. exactly the labelled OOB write.
- post_benign: the guard fires ("Invalid JPEG-XS header size 4294967040 > packet size 8"), av_read_frame returns AVERROR_INVALIDDATA, and the process exits cleanly (0) with no sanitizer report - the labelled OOB write no longer occurs.

Note on methodology: I initially reproduced this with the full ffmpeg CLI (-i poc.ts -copy_unknown -map 0 -c copy -f null /dev/null). That command reproduced the SEGV identically in post_intro, but in post_benign it uncovered a second, unrelated defect: new_pes_packet's early-return-on-error path sets pkt->buf = pes->buffer (a raw pointer copy) before the header_size check, and on the error path never does `pes->buffer = NULL`, so pkt->buf and pes->buffer end up aliasing the same AVBufferRef; when the caller later av_packet_unref()s the packet (immediately, or during avformat_find_stream_info's duration-estimation seek/flush, or at close), that buffer is freed while pes->buffer still points at it, producing a heap-use-after-free (ASan: buffer_replace/av_buffer_unref, libavutil/buffer.c:121, via handle_packets mpegts.c:3132) - a different bug in a different function/stack with a different signature (UAF vs wild-pointer SEGV) than the labelled BufferOverflow, and one that is absent from post_intro entirely (it only exists once the fix's error-return path exists). To keep the pre/post_intro/post_benign comparison strictly about the labelled bug, I isolated it with a minimal harness that performs a single av_read_frame and exits without invoking the unrelated cleanup path; this gives a clean, unambiguous, reproducible signal per version using the identical input and invocation logic across all three builds, matching the task's own repro description (stream_id 0xbd, stream_type 0x32, header_size 0xFFFFFF00, 'jxes' marker).

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=3b1214a89767  note=build cached
  command=cd /work && clang -g -O1 -fsanitize=address -fno-omit-frame-pointer -I. /poc/poc.c -o /tmp/poc_bin -Llibavformat -Llibavcodec -Llibavutil -Llibswresample -Llibswscale -Llibavfilter -Llibavdevice -lavformat -lavcodec -lavutil -lswresample -lm -lz -pthread -latomic -fsanitize=address && /tmp/poc_bin /poc/poc.ts
  poc_sha256=ce304fd6448f46096a9f784b3e2a9f8a7bd32de94e5e28da89dd821c2603ee40
  source_integrity=True
  output_tail:
    VERIFY_EXIT=0
    
    [mpegts @ 0x616000000080] Format mpegts detected only with low score of 2, misdetection possible!
    [mpegts @ 0x616000000080] Could not detect TS packet size, defaulting to non-FEC/DVHS
    [mpegts @ 0x616000000080] probed stream 0 failed
    av_read_frame returned 0
    got packet size=8
    PRE_CLOSE_OK
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=536475ea0582  note=build cached
  command=cd /work && clang -g -O1 -fsanitize=address -fno-omit-frame-pointer -I. /poc/poc.c -o /tmp/poc_bin -Llibavformat -Llibavcodec -Llibavutil -Llibswresample -Llibswscale -Llibavfilter -Llibavdevice -lavformat -lavcodec -lavutil -lswresample -lm -lz -pthread -latomic -fsanitize=address && /tmp/poc_bin /poc/poc.ts
  poc_sha256=ce304fd6448f46096a9f784b3e2a9f8a7bd32de94e5e28da89dd821c2603ee40
  source_integrity=True
  sanitizer:
    ERIFY_EXIT=134
    
    [mpegts @ 0x616000000080] Format mpegts detected only with low score of 2, misdetection possible!
    [mpegts @ 0x616000000080] Could not detect TS packet size, defaulting to non-FEC/DVHS
    AddressSanitizer:DEADLYSIGNAL
    =================================================================
    ==8==ERROR: AddressSanitizer: SEGV on unknown address 0x60d100000068 (pc 0x7fd5b5e6bfe4 bp 0x7ffce2d9f6f0 sp 0x7ffce2d9eeb8 T0)
    ==8==The signal is caused by a WRITE memory access.
        #0 0x7fd5b5e6bfe4  string/../sysdeps/x86_64/multiarch/memset-vec-unaligned-erms.S:137
        #1 0x562f0d118e23 in __asan_memset (/tmp/poc_bin+0x688e23) (BuildId: 5043dbdd481ebe2bb6244f6c8ecdaf96e52ab91e)
        #2 0x562f0d3d3bf7 in new_pes_packet /work/libavformat/mpegts.c:1042:5
        #3 0x562f0d3d0ad4 in mpegts_push_data /work/libavformat/mpegts.c:1431:27
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=3b1214a89767  note=build cached
  command=cd /work && clang -g -O1 -fsanitize=address -fno-omit-frame-pointer -I. /poc/poc.c -o /tmp/poc_bin -Llibavformat -Llibavcodec -Llibavutil -Llibswresample -Llibswscale -Llibavfilter -Llibavdevice -lavformat -lavcodec -lavutil -lswresample -lm -lz -pthread -latomic -fsanitize=address && /tmp/poc_bin /poc/poc.ts
  poc_sha256=ce304fd6448f46096a9f784b3e2a9f8a7bd32de94e5e28da89dd821c2603ee40
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    VERIFY_EXIT=0
    
    [mpegts @ 0x616000000080] Format mpegts detected only with low score of 2, misdetection possible!
    [mpegts @ 0x616000000080] Could not detect TS packet size, defaulting to non-FEC/DVHS
    [mpegts @ 0x616000000080] Invalid JPEG-XS header size 4294967040 > packet size 8
    av_read_frame returned -1094995529
    PRE_CLOSE_OK
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
