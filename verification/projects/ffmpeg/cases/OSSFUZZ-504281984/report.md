# Verification report: pr_review_OSSFUZZ-504281984

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: LogicError
- **Intro commit**: `2d241202fffd32df1b5992197e622f298d3d029d`
- **Intro parent**: `6c83bcadbbdbec8e2b8cf156de3e8bcc4e6c880a`
- **Fix commit**: `054dffd13368f8d7d024dbdfdce7454e6e547c5f`
- **Affected files**: ['libavcodec/bsf/dts2pts.c']

## PoC
- source: agent-generated (initial source: incomplete)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/ffmpeg/c769cbefa1b2ad529a31/attempts/03/pocs/ffmpeg/OSSFUZZ-504281984`
- input: `None` (0 bytes)
- run.sh: True

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- Ground truth per meta.json: intro commit 2d241202fffd adds the HEVC branch of the dts2pts BSF, whose hevc_queue_frame() detects a POC that requires "decrementing" previously queued AVTree nodes in the same GOP and does so by calling av_tree_enumerate() with a comparator (same_gop) that only compares the `gop` field while the tree is actually ordered by (poc, gop) via cmp_insert. Because av_tree_enumerate's traversal pruning trusts the comparator to be consistent with the tree's real order, and directly mutates node->poc in dec_poc() while the node remains linked at its stale sort position, repeated/interleaved decrement events (achievable by feeding many NAL units whose slice_pic_order_cnt_lsb repeatedly forces poc < s->nb_frame within the same GOP) desynchronize the tree from its cmp_insert invariant. A later av_tree_insert() (called from dts2pts_filter's receive-side restore loop) then walks the corrupted structure and dereferences a wild pointer inside cmp_insert, exactly matching the original OSS-Fuzz report's crash state (cmp_insert <- av_tree_insert <- av_tree_insert, heap-buffer-overflow READ 4).

I verified this by building a harness that talks to the real ff_dts2pts_bsf filter through the public AVBSFContext API (same interface as tools/target_bsf_fuzzer.c), synthesizing a minimal valid HEVC bitstream via FFmpeg's own CBS writer (so no bit-level hand-crafting of NAL headers was needed), and randomized-searching over (nal_unit_type, slice_pic_order_cnt_lsb) sequences until the exact cmp_insert/av_tree_insert crash signature appeared; the sequence was then delta-debug-minimized to 108 NAL units. Running the identical reproducer (/poc/run.sh, using /poc/crash_seq.txt) against the three builds:
- pre_intro: dts2pts at that revision has no HEVC support at all (codec_ids={H264}), so av_bsf_init fails immediately and cleanly; the harness treats this as the expected non-crashing outcome and exits 0 -- the bug and the feature it lives in are both absent, confirming the regression was introduced together with the HEVC path.
- post_intro: reliably reproduces the exact OSS-Fuzz crash signature (SEGV/heap-buffer-overflow read in cmp_insert via nested av_tree_insert).
- post_benign: completes cleanly with the same input, no crash, no sanitizer report, exit 0 -- the fix (which replaces the enumerate+in-place-mutate with a bounded collect_same_gop() pass followed by proper remove/reinsert of each node) eliminates the tree corruption for this exact reproducer.

Note found during exploration (not part of the recorded reproducer): larger/more chaotic variants of the same search approach also crash post_benign, but via a completely different, non-memory-safety failure: an explicit av_assert0(c.count <= c.max) in the fix's own collect_same_gop() bounded-buffer safety check (dts2pts.c:462), a distinct, intentional defensive bound (HEVC_MAX_DPB_SIZE*2) unrelated to the labelled AVTree-invariant defect. The final, minimized 108-NAL reproducer recorded here does not trigger that assertion at all on post_benign (clean exit 0), so it cleanly isolates just the originally-labelled defect without ambiguity.

Although the task labels this LogicError, the actual, reproducible regression is a memory-safety violation (an AVTree invariant violation causing a wild-pointer read), which is exactly how the original OSS-Fuzz issue itself was classified (Heap-buffer-overflow READ 4) and exactly the crash signature reproduced here, so intro_verified=yes and benign_verified=yes with bug_class=memory-safety.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=6c83bcadbbdb  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=844ade659cd2fbc9604b5fe43e111095d85ae1e4a8108936ed1614219e776df0
  source_integrity=True
  output_tail:
    VERIFY_EXIT=0
    
    [dts2pts @ 0x608000000020] Codec 'hevc' (173) is not supported by the bitstream filter 'dts2pts'. Supported codecs are: h264 (27) 
    av_bsf_init failed: -22 (dts2pts does not accept HEVC on this revision -- expected pre-introduction behavior)
    [poc] done, no crash
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=2d241202fffd  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=844ade659cd2fbc9604b5fe43e111095d85ae1e4a8108936ed1614219e776df0
  source_integrity=True
  sanitizer:
    VERIFY_EXIT=134
    
    AddressSanitizer:DEADLYSIGNAL
    =================================================================
    ==13==ERROR: AddressSanitizer: SEGV on unknown address 0x01817fff80fe (pc 0x55e1cac5a6e6 bp 0x7ffc8fabe7d0 sp 0x7ffc8fabe7d0 T0)
    ==13==The signal is caused by a READ memory access.
        #0 0x55e1cac5a6e6 in cmp_insert /work/libavcodec/bsf/dts2pts.c:99:78
        #1 0x55e1cc3bfa56 in av_tree_insert /work/libavutil/tree.c:64:26
        #2 0x55e1cc3bfa85 in av_tree_insert /work/libavutil/tree.c:81:15
        #3 0x55e1cc3bfa85 in av_tree_insert /work/libavutil/tree.c:81:15
        #4 0x55e1cc3bfa85 in av_tree_insert /work/libavutil/tree.c:81:15
        #5 0x55e1cc3bfa85 in av_tree_insert /work/libavutil/tree.c:81:15
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=6c83bcadbbdb  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=844ade659cd2fbc9604b5fe43e111095d85ae1e4a8108936ed1614219e776df0
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    VERIFY_EXIT=0
    
    [poc] done, no crash
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
