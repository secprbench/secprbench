# Verification report: pr_review_OSSFUZZ-418421333

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: OutOfBoundsRead
- **Intro commit**: `821717c3fe1ce7fd022077669a1380634fb102d0`
- **Intro parent**: `0c79a091e4dcf5ad00d02c94babab2499bd65793`
- **Fix commit**: `f09c834a7d01dfde9369551b2767c001846a396f`
- **Affected files**: ['libavcodec/cbs_apv_syntax_template.c']

## PoC
- source: agent-generated (initial source: incomplete)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/ffmpeg/168ecafcd4dabb80b910/attempts/01/pocs/ffmpeg/OSSFUZZ-418421333`
- input: `input.apv` (46 bytes)
- run.sh: True

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- Build-environment note: this benchmark's source snapshot is "incomplete" (per meta.json) — the real APV decoder (apv_dec.c, ff_apv_entropy_decode_block, etc.) referenced by the original OSS-Fuzz crash trace does not exist anywhere in this tree, and configure does not auto-select CONFIG_CBS_APV (no decoder/bsf in this pruned tree selects it), so cbs_apv.c/cbs_apv_syntax_template.c are not linked into the default libavcodec.a in any of the three built revisions even though the source file itself is present (unmodified) for post_intro/post_benign. run.sh therefore compiles the existing, untouched libavcodec/cbs_apv.c and libavcodec/cbs.c directly with -DCBS_APV=1 (only a compile-time override of the very macro configure would otherwise define) and links them with a tiny added harness (poc.c) that calls only public CBS API functions. No tracked target source was edited; the same unmodified target files and the same crafted input (/poc/input.apv) were used, unchanged, for all three revisions via run_poc.

Results (via run_poc):
- pre_intro (0c79a091e4dc): run.sh detects that libavcodec/cbs_apv.c does not exist in this revision at all ("cbs_apv.c not present ... feature not yet added"); exit 0, no crash. The tile() function containing the flaw was not yet written, so this specific bug cannot be present — a genuine introduction, not merely an untested path.
- post_intro (821717c3fe1c): harness built and run; ff_cbs_read() succeeds (the unchecked tile() read path silently accepts tile_data_size=200000 even though only a few bytes remain in the buffer — skip_bits_long() is called without checking get_bits_left(), exactly per root_cause). ff_cbs_write_fragment_data() then re-serializes the parsed fragment; cbs_apv_write_tile() (cbs_apv_syntax_template.c:232, the write branch of the very same tile() function) calls ff_copy_bits(rw, current->tile_data[c], comp_size*8), which memcpy's 199998 bytes starting from a pointer sitting at the very end of the 110-byte heap buffer that held the parsed input. AddressSanitizer reports "heap-buffer-overflow ... READ of size 199998 ... 0 bytes to the right of 110-byte region", with the crashing frame directly in cbs_apv_write_tile -> cbs_apv_write_frame -> cbs_apv_write_unit -> cbs_write_unit_data -> ff_cbs_write_fragment_data -> main. crashed=True.
- post_benign (companion of fix f09c834a7d01): identical harness, identical binary input via run_poc. ff_cbs_read() now fails cleanly with AVERROR_INVALIDDATA ("Failed to read unit 0 (type 1)") because the fixed tile() checks get_bits_left(rw) < 8LL*comp_size before accepting tile_data_size, rejecting the malformed size at read time. Program exits 0, no ASan report — ff_cbs_write_fragment_data (and therefore ff_copy_bits) is never reached. crashed=False.

This satisfies the required invariant: the identical reproducer (run.sh + input.apv, run via run_poc) yields the sanitizer report only in post_intro; pre_intro cannot even reach the code (file doesn't exist → no regression possible) and post_benign completes cleanly without the report. The crash mechanism (unchecked tile_data_size leading to an unbounded read of tile-component bytes) is exactly the root cause described in meta.json, and the crash is an explicit ASan heap-buffer-overflow READ, matching the OutOfBoundsRead label — observed via the CBS read+write round-trip sink (ff_copy_bits) rather than the (absent-from-this-tree) APV decoder's entropy-decode sink used by the original report, but this is the same flaw and the same fix commit (which folds together multiple OSS-Fuzz IDs, including 418804929, which crashes via this exact ff_copy_bits call site).

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=0c79a091e4dc  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=33d0aa054ad554e7d56eb3b3e0020b0faa484e7a708bd0b39b73b346514215d1
  source_integrity=True
  output_tail:
    cbs_apv.c not present in this revision (pre-intro: feature not yet added)
    NO_CBS_APV_SOURCE
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=1  poc_ran=True  patched=False
  commit=821717c3fe1c  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=33d0aa054ad554e7d56eb3b3e0020b0faa484e7a708bd0b39b73b346514215d1
  source_integrity=True
  sanitizer:
    VERIFY_EXIT=1
    
    ff_cbs_read -> 0 (nb_units=1)
    =================================================================
    ==14==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x60c00000016e at pc 0x561c4859ca07 bp 0x7ffe51378cb0 sp 0x7ffe51378480
    READ of size 199998 at 0x60c00000016e thread T0
        #0 0x561c4859ca06 in __asan_memcpy (/tmp/poc+0x4c5a06) (BuildId: 537b6d33cab3ce8db8059937776a3c6ba2ca110b)
        #1 0x561c485eb27f in ff_copy_bits /work/libavcodec/bitstream.c:67:9
        #2 0x561c485e145e in cbs_apv_write_tile /work/./libavcodec/cbs_apv_syntax_template.c:232:9
        #3 0x561c485e145e in cbs_apv_write_frame /work/./libavcodec/cbs_apv_syntax_template.c:254:9
        #4 0x561c485e145e in cbs_apv_write_unit /work/libavcodec/cbs_apv.c:330:19
        #5 0x561c485e529c in cbs_write_unit_data /work/libavcodec/cbs.c:384:11
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=0c79a091e4dc  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=33d0aa054ad554e7d56eb3b3e0020b0faa484e7a708bd0b39b73b346514215d1
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    VERIFY_EXIT=0
    
    Failed to read unit 0 (type 1).
    ff_cbs_read -> -1094995529 (nb_units=1)
    read failed, stopping (no bug reachable)
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
