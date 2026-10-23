# Verification report: pr_review_OSSFUZZ-428055715

- **Status**: `inconclusive`
- **Intro verified**: None
- **Benign verified**: None
- **Bug type**: IntegerOverflow
- **Intro commit**: `7ef9d31071021c05e6b792af3f25b7b9ceaa9258`
- **Intro parent**: `60be62d29388fdc681540dff387e0304e610bf39`
- **Fix commit**: `08816b93760f43433a07e980fa9eeab4135de78c`
- **Affected files**: ['libavcodec/osq.c']

## PoC
- source: agent-generated (initial source: incomplete)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/ffmpeg/c9ae3b8d6682781a2269/attempts/03/pocs/ffmpeg/OSSFUZZ-428055715`
- input: `None` (0 bytes)
- run.sh: True

## Findings

- The agent claim lacks a matching admissible three-version oracle.
- pre_intro (60be62d29388): libavcodec/osq.c does not exist at all (confirmed via grep/find: no osq.c file, AV_CODEC_ID_OSQ not defined in codec_id.h). The OSQ decoder was added wholesale by the intro commit, so the flaw could not exist before introduction. run_poc on pre_intro cleanly prints "AV_CODEC_ID_OSQ not present in this revision" and exits 42, never reaching any decode path (no UBSan/ASan report) -- the only honest outcome for a commit that introduces a brand-new decoder together with its bug.

post_intro (7ef9d3107102): libavcodec/osq.c contains `dst[n] = av_clip_uint8(src[n] + 0x80);` performed in plain 32-bit `int` arithmetic. run_poc on post_intro reproduces the reported UBSan finding precisely: "libavcodec/osq.c:369:47: runtime error: signed integer overflow: 2147483587 + 128 cannot be represented in type 'int'", crash stack osq_decode_block -> osq_receive_frame -> decode_receive_frame_internal -> ff_decode_receive_frame -> avcodec_receive_frame, matching the OSS-Fuzz report's crash state (osq_receive_frame / ff_decode_receive_frame_internal / decode_receive_frame_internal) and the fix commit's own UBSan message template ("signed integer overflow: 2147483565 + 128 cannot be represented in type 'int'") almost verbatim (2147483587 vs 2147483565, both ~INT_MAX-60, same +128 offset, same file/line/function). Process aborts with exit 134. This is a genuine target-reachability confirmation: the crash is inside the exact OSQ sample-format-conversion statement named in the root cause.

post_benign (companion fix, equivalent to fix commit 08816b93760f): libavcodec/osq.c now reads `dst[n] = av_clip_uint8(src[n] + 0x80ll);` (64-bit addition, no UB). run_poc with the identical run.sh/poc.c completes cleanly (avcodec_send_packet/avcodec_receive_frame both succeed, 16 samples decoded, exit 0), producing zero UBSan or ASan reports under the same -fsanitize=signed-integer-overflow instrumentation that caught the bug in post_intro.

Because the vulnerable code was entirely new in the intro commit, pre_intro cannot exhibit the bug by construction (a clean "feature absent" exit is the only possible honest outcome there), while post_intro crashes and post_benign does not, under the identical PoC/command and identical sanitizer instrumentation -- satisfying the required intro/benign comparison invariant.

## Agent oracle

- machine gate: inconclusive (unproven)
- basis: The agent claim lacks a matching admissible three-version oracle.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=42  poc_ran=True  patched=False
  commit=60be62d29388  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=b25acaf7310497ceb493aec2757496d95bd0fa32b85f938cfa8f9330846b5efe
  source_integrity=True
  output_tail:
    HAVE_OSQ=0
    VERIFY_EXIT=42
    
    /usr/bin/ld: /usr/lib/llvm-14/lib/clang/14.0.0/lib/linux/libclang_rt.asan-x86_64.a(asan_interceptors_vfork.S.o): warning: common of `__interception::real_vfork' overridden by definition from /usr/lib/llvm-14/lib/clang/14.0.0/lib/linux/libclang_rt.asan-x86_64.a(asan_interceptors.cpp.o)
    PoC-SKIP: AV_CODEC_ID_OSQ not present in this revision (decoder absent)
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=7ef9d3107102  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=b25acaf7310497ceb493aec2757496d95bd0fa32b85f938cfa8f9330846b5efe
  source_integrity=True
  sanitizer:
    mple[14] residue=0 acc=1610612733
    sample[15] residue=536870854 acc=2147483587
    packet size=63 bytes, predicted final sample=2147483587
    send_packet ret=0
    send_packet(EOF) ret=0
    libavcodec/osq.c:369:47: runtime error: signed integer overflow: 2147483587 + 128 cannot be represented in type 'int'
        #0 0x561afc3dcc20 in osq_decode_block /work/libavcodec/osq.c:369:47
        #1 0x561afc3dcc20 in osq_receive_frame /work/libavcodec/osq.c:435:16
        #2 0x561afc614cd0 in decode_receive_frame_internal /work/libavcodec/decode.c:623:15
        #3 0x561afc616281 in ff_decode_receive_frame /work/libavcodec/decode.c:804:15
        #4 0x561afc444e7f in avcodec_receive_frame /work/libavcodec/avcodec.c:715:16
        #5 0x561afc3d80cf in main /poc/poc.c:165:11
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=60be62d29388  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=b25acaf7310497ceb493aec2757496d95bd0fa32b85f938cfa8f9330846b5efe
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    sample[2] residue=536870911 acc=1610612733
    sample[3] residue=0 acc=1610612733
    sample[4] residue=0 acc=1610612733
    sample[5] residue=0 acc=1610612733
    sample[6] residue=0 acc=1610612733
    sample[7] residue=0 acc=1610612733
    sample[8] residue=0 acc=1610612733
    sample[9] residue=0 acc=1610612733
    sample[10] residue=0 acc=1610612733
    sample[11] residue=0 acc=1610612733
    sample[12] residue=0 acc=1610612733
    sample[13] residue=0 acc=1610612733
    sample[14] residue=0 acc=1610612733
    sample[15] residue=536870854 acc=2147483587
    packet size=63 bytes, predicted final sample=2147483587
    send_packet ret=0
    send_packet(EOF) ret=0
    receive_frame ret=0 nb_samples=16
    decoded u8 samples: 255 255 255 255 255 255 255 255 255 255 255 255 255 255 255 0
    PoC-DONE
```

## Interpretation

The available evidence does not establish both labels. Inspect the findings and per-version results for the limiting reason.
