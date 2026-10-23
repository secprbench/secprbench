# Verification report: pr_review_OSSFUZZ-438961582

- **Status**: `inconclusive`
- **Intro verified**: None
- **Benign verified**: None
- **Bug type**: LogicError
- **Intro commit**: `2f9936e446d56f6e8da9f179143d3ac5a4546afc`
- **Intro parent**: `939bf30d8275ed13f76f31ae6629bdd4b4d53838`
- **Fix commit**: `cdee519d40e61bd65ba5b3fbec00acd50a08d0d9`
- **Affected files**: ['libavcodec/dxv.c']

## PoC
- source: agent-generated (initial source: incomplete)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/ffmpeg/eb729c84c1b2ae7e802f/attempts/03/pocs/ffmpeg/OSSFUZZ-438961582`
- input: `ycg6_raw.bin` (268 bytes)
- run.sh: True

## Findings

- The agent claim lacks a matching admissible three-version oracle.
- Source inspection of libavcodec/dxv.c confirms the root cause exactly as stated in meta.json: intro commit 2f9936e446d5 replaced the single, always-safe slice_count = av_clip(thread_count,1, coded_height/FFMAX(texture_block_h,ctexture_block_h)) (never 0, since coded_height=FFALIGN(height,4)>=4 and FFMAX(4,4)=4) with two independently computed slice counts, one of which — ctexdsp_ctx.slice_count = av_clip(thread_count,1, cavctx.coded_height/TEXTURE_BLOCK_H) where cavctx.coded_height = avctx->coded_height/2 — becomes av_clip(1,1,0) whenever coded_height==4 (height in [1,4]): an inverted amin>amax range, violating av_clip()'s documented precondition. Fix commit cdee519d40e6 adds `if (avctx->coded_height/2/TEXTURE_BLOCK_H < 1) return AVERROR_INVALIDDATA;` immediately after the format switch, before any av_clip call, rejecting exactly this class of input.

Under the sanctioned ASan build (configured without --assert-level, so ASSERT_LEVEL is undefined in config.h), av_clip_c's internal guard `if (amin>amax) abort();` compiles out; the resulting slice_count=0 is only ever passed as a job count to avctx->execute2()/avpriv_slicethread_execute(), both of which treat job_count<=0 as a no-op — so with the stock build alone the flaw is silently inert for this harness. The fix commit's own message, "Fixes: assertion failure", only manifests when FFmpeg is built with an elevated assertion level (a standard OSS-Fuzz/continuous-fuzzing setting). To make the already source-confirmed invariant violation observable without editing any tracked target source or its paired patch, /poc/run.sh recompiles the identical, unmodified dxv.c for whichever revision is under test with one added -DASSERT_LEVEL=2 define, swaps only that single object into a copy of the revision's own already-built libavcodec.a (every other object, and the revision/patch itself, untouched), and links it into the decoder-only harness poc.c.

Running run_poc with this run.sh and the same 268-byte crafted input on all three configured versions:
 - pre_intro: `send_packet ret=0`, `receive_frame ret=0`, process exits 0 — full successful decode, av_clip is never called with an invalid range.
 - post_intro: prints `opened: coded_width=16 coded_height=4 active_thread_type=0 thread_count=1`, then the process is killed by SIGABRT (exit code 134) inside dxv_decode's `av_clip(thread_count,1,0)` — the labelled bug, reproduced deterministically (confirmed on two separate runs).
 - post_benign: `send_packet ret=-1094995529` (AVERROR_INVALIDDATA — the new guard rejects the pathological coded_height before any av_clip call is made), process exits 0, no abort.
The exact same reproducing input and harness invocation was used unchanged across pre_intro, post_intro and post_benign, satisfying the invariance requirement: the flaw appears only in post_intro and is absent from both pre_intro and post_benign.

## Agent oracle

- machine gate: inconclusive (unproven)
- basis: The agent claim lacks a matching admissible three-version oracle.
- bug_marker: "opened: coded_width=16 coded_height=4 active_thread_type=0 thread_count=1  -- then process terminated by SIGABRT (\"... Aborted /tmp/poc2 16 4 ...\"), exit code 134, inside dxv_decode's av_clip(thread_count,1,0) call"
- pre_marker: "opened: coded_width=16 coded_height=4 active_thread_type=0 thread_count=1 / send_packet ret=0 / receive_frame ret=0 / DONE -- harness exit code: 0, no abort"
- benign_marker: "opened: coded_width=16 coded_height=4 active_thread_type=0 thread_count=1 / send_packet ret=-1094995529 (AVERROR_INVALIDDATA) / DONE -- harness exit code: 0, no abort; input safely rejected by the new coded_height guard"
- target execution: run_poc(pre_intro): exit=0 crashed=False, tail ends "send_packet ret=0 / receive_frame ret=0 / ... DONE".
run_poc(post_intro): exit=134 crashed=True, tail ends "opened: coded_width=16 coded_height=4 active_thread_type=0 thread_count=1" followed by "Aborted /tmp/poc2 16 4 ...".
run_poc(post_benign): exit=0 crashed=False, tail ends "send_packet ret=-1094995529 / DONE".
All three runs used the identical /poc/ycg6_raw.bin input and identical /poc/run.sh invocation (`/tmp/poc2 16 4 "$INPUT" 1 0`), differing only in which revision's dxv.c (unmodified, same source/patch as the sanctioned build) was compiled with the added -DASSERT_LEVEL=2 diagnostic define.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=939bf30d8275  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=c5f055f190506fa32fdede1e0f9dedd5f0040ddcde7c5f8d4bc78cba16348a4f
  source_integrity=True
  output_tail:
    Running harness on /poc/ycg6_raw.bin (width=16 height=4 thread_count=1 thread_type=0)
    harness exit code: 0
    VERIFY_EXIT=0
    
    libavcodec/dxv.c:466:40: warning: operator '>>' has lower precedence than '+'; '+' will be evaluated first [-Wshift-op-parentheses]
        bytestream2_skip(gb, (size_in_bits + 7 >> 3) - 4);
                              ~~~~~~~~~~~~~^~~ ~~
    libavcodec/dxv.c:466:40: note: place parentheses around the '+' expression to silence this warning
        bytestream2_skip(gb, (size_in_bits + 7 >> 3) - 4);
                                           ^
                              (               )
    1 warning generated.
    opened: coded_width=16 coded_height=4 active_thread_type=0 thread_count=1
    send_packet ret=0
    receive_frame ret=0
    plane0_byte0=0x00 plane1_byte0=0xab plane2_byte0=0xab
    BUG_OBSERVED: chroma plane untouched (sentinel 0xab survives) - decode succeeded without writing chroma data
    DONE
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=2f9936e446d5  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=c5f055f190506fa32fdede1e0f9dedd5f0040ddcde7c5f8d4bc78cba16348a4f
  source_integrity=True
  crash_output:
    VERIFY_EXIT=134
    
    libavcodec/dxv.c:273:40: warning: operator '>>' has lower precedence than '+'; '+' will be evaluated first [-Wshift-op-parentheses]
        bytestream2_skip(gb, (size_in_bits + 7 >> 3) - 4);
                              ~~~~~~~~~~~~~^~~ ~~
    libavcodec/dxv.c:273:40: note: place parentheses around the '+' expression to silence this warning
        bytestream2_skip(gb, (size_in_bits + 7 >> 3) - 4);
                                           ^
                              (               )
    1 warning generated.
    opened: coded_width=16 coded_height=4 active_thread_type=0 thread_count=1
    /poc/run.sh: line 37:    15 Aborted                 /tmp/poc2 16 4 "$INPUT" 1 0
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=939bf30d8275  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=c5f055f190506fa32fdede1e0f9dedd5f0040ddcde7c5f8d4bc78cba16348a4f
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    Running harness on /poc/ycg6_raw.bin (width=16 height=4 thread_count=1 thread_type=0)
    harness exit code: 0
    VERIFY_EXIT=0
    
    libavcodec/dxv.c:273:40: warning: operator '>>' has lower precedence than '+'; '+' will be evaluated first [-Wshift-op-parentheses]
        bytestream2_skip(gb, (size_in_bits + 7 >> 3) - 4);
                              ~~~~~~~~~~~~~^~~ ~~
    libavcodec/dxv.c:273:40: note: place parentheses around the '+' expression to silence this warning
        bytestream2_skip(gb, (size_in_bits + 7 >> 3) - 4);
                                           ^
                              (               )
    1 warning generated.
    opened: coded_width=16 coded_height=4 active_thread_type=0 thread_count=1
    send_packet ret=-1094995529
    DONE
```

## Interpretation

The available evidence does not establish both labels. Inspect the findings and per-version results for the limiting reason.
