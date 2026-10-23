# Verification report: pr_review_REPORT-c9e93df4eed93fe0

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: BufferOverflow
- **Intro commit**: `589b3ed943d46ba163cea383634d67319af11cba`
- **Intro parent**: `5674879db5ea411b42e55c3906fa586f540bf637`
- **Fix commit**: `c9e93df4eed93fe0044c52d953688c4180de1d48`
- **Affected files**: ['libavcodec/prores_raw.c']

## PoC
- source: agent-generated (initial source: incomplete)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/ffmpeg/4b8bc490c49822978729/attempts/01/pocs/ffmpeg/REPORT-c9e93df4eed93fe0`
- input: `poc.raw` (120 bytes)
- run.sh: False

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- meta.json's root cause: in decode_frame(), avctx->coded_width/coded_height are set to the 16-byte-aligned frame dimensions BEFORE the call to ff_set_dimensions(avctx, w, h), which internally overwrites those same fields back to the unaligned w/h whenever the resolution changes (always true on the first frame, since avctx->width/height start at 0). The output buffer is then allocated (ff_thread_get_buffer) using the unaligned coded_height, while decode_tile()/decode_comp() unconditionally write a full 16-row tile at tile->y regardless of avctx->height, so for any height not a multiple of 16 the last tile row overflows the buffer.

Verification (identical 120-byte input + identical harness/command run via run_poc on all three configured versions):
- pre_intro (parent 5674879db5ea): exit=0, crashed=False. Output "no decoder (codepath not present on this revision)": libavcodec/prores_raw.c does not exist in this revision (confirmed by directory listing: only prores_raw_parser.c/proresdec.c/proresdsp.c etc. are present, no prores_raw.c) — the whole ProRes RAW decoder is new code introduced by the intro commit, so the flaw cannot be present here. Clean, non-crashing run.
- post_intro (589b3ed943d4): exit=134, crashed=True. Clear AddressSanitizer heap-buffer-overflow ("WRITE of size 2 ... 233 bytes to the right of 12823-byte region") in put_pixel_bayer_12 (proresdsp.c:107), reached from decode_comp/decode_tile/decode_tiles/decode_frame (prores_raw.c:243/278/311/482) -> avcodec_default_get_buffer2. This matches the fix commit's own description ("Fixes: Heap-buffer-overflow", OssFuzz 438771336) and meta.json's stated root cause exactly (buffer allocated for unaligned height 50 while tile writes reach rows 48-63, i.e. need aligned height 64).
- post_benign (fix reorders the coded_width/coded_height assignment to run AFTER ff_set_dimensions): exit=0, crashed=False, no sanitizer report. Diagnostic output confirms coded_h=64 (correctly 16-aligned) instead of the buggy 50, and avcodec_receive_frame returns a frame successfully.

The crash appears only in post_intro under the identical input/command; pre_intro (feature absent) and post_benign (fixed) both complete cleanly, satisfying the required invariance across the three revisions.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=5674879db5ea  note=build cached
  command=cd /tmp && cp /poc/poc.c . && clang -g -O1 -fsanitize=address -fno-omit-frame-pointer -I/work -I/work/libavutil -o poc poc.c -L/work/libavcodec -L/work/libavformat -L/work/libavfilter -L/work/libavdevice -L/work/libswresample -L/work/libswscale -L/work/libavutil -lavcodec -lavformat -lavfilter -lavdevice -lswresample -lswscale -lavutil -lm -lz -pthread -fsanitize=address && ./poc $INPUT
  poc_sha256=163a5405c683e83fb74c9225d35338ed7c6bfad4736437c5f59ab26b17c3cf90
  source_integrity=True
  output_tail:
    VERIFY_EXIT=0
    
    no decoder (codepath not present on this revision)
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=589b3ed943d4  note=build cached
  command=cd /tmp && cp /poc/poc.c . && clang -g -O1 -fsanitize=address -fno-omit-frame-pointer -I/work -I/work/libavutil -o poc poc.c -L/work/libavcodec -L/work/libavformat -L/work/libavfilter -L/work/libavdevice -L/work/libswresample -L/work/libswscale -L/work/libavutil -lavcodec -lavformat -lavfilter -lavdevice -lswresample -lswscale -lavutil -lm -lz -pthread -fsanitize=address && ./poc $INPUT
  poc_sha256=163a5405c683e83fb74c9225d35338ed7c6bfad4736437c5f59ab26b17c3cf90
  source_integrity=True
  sanitizer:
    VERIFY_EXIT=134
    
    [prores_raw @ 0x618000000080] picture resolution change: 0x0 -> 128x50
    =================================================================
    ==8==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x627000003400 at pc 0x561a48c469b2 bp 0x7fff3ec79930 sp 0x7fff3ec79928
    WRITE of size 2 at 0x627000003400 thread T0
        #0 0x561a48c469b1 in put_pixel_bayer_12 /work/libavcodec/proresdsp.c:107:22
        #1 0x561a48c469b1 in prores_idct_put_bayer_12_c /work/libavcodec/proresdsp.c:137:5
        #2 0x561a48c3f598 in decode_comp /work/libavcodec/prores_raw.c:243:9
        #3 0x561a48c3ea70 in decode_tile /work/libavcodec/prores_raw.c:278:11
        #4 0x561a48c3ea70 in decode_tiles /work/libavcodec/prores_raw.c:311:12
        #5 0x561a48403b90 in avcodec_default_execute2 /work/libavcodec/avcodec.c:92:17
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=5674879db5ea  note=build cached
  command=cd /tmp && cp /poc/poc.c . && clang -g -O1 -fsanitize=address -fno-omit-frame-pointer -I/work -I/work/libavutil -o poc poc.c -L/work/libavcodec -L/work/libavformat -L/work/libavfilter -L/work/libavdevice -L/work/libswresample -L/work/libswscale -L/work/libavutil -lavcodec -lavformat -lavfilter -lavdevice -lswresample -lswscale -lavutil -lm -lz -pthread -fsanitize=address && ./poc $INPUT
  poc_sha256=163a5405c683e83fb74c9225d35338ed7c6bfad4736437c5f59ab26b17c3cf90
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    VERIFY_EXIT=0
    
    [prores_raw @ 0x618000000080] picture resolution change: 0x0 -> 128x50
    send_packet ret=0
    receive_frame ret=0 w=128 h=50 coded_w=128 coded_h=64
    DONE
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
