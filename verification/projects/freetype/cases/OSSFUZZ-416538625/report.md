# Verification report: pr_review_OSSFUZZ-416538625

- **Status**: `inconclusive`
- **Intro verified**: None
- **Benign verified**: None
- **Bug type**: LogicError
- **Intro commit**: `5cf01aa2b26727abd97ef202a3687cd7a43819c3`
- **Intro parent**: `f93a897afedf4a634c74d3d2871519e675ee0d83`
- **Fix commit**: `6fa8725a416735a9cf62b68b8aa146144c1e471e`
- **Affected files**: ['src/truetype/ttgload.c', 'src/cff/cffgload.c', 'src/sfnt/ttsvg.c']

## PoC
- source: agent-final (initial source: locally_fix_derived)
- dir: `/research-data/secprbench/freetype-svg-alloc-normal-import-v1/verification/cases/freetype/f4a3f154a629babbef5b/attempts/01/pocs/freetype/OSSFUZZ-416538625`
- input: `svg-alloc.ttf` (887645 bytes)
- run.sh: True

## Findings

- The agent claim lacks a matching admissible three-version oracle.
- Ran the identical oracle binary (built fresh against each revision's libfreetype.a per run.sh) against the identical svg-alloc.ttf input on pre_intro, post_intro, and post_benign. Results cleanly match the labelled regression: pre_intro reports large_alloc_count=0 (the glyph loader did not yet call tt_face_load_svg_doc at all prior to the intro commit, so the vulnerable path is unreached), post_intro reports large_alloc_count=1 max_large_bytes=134217728 (the newly-added call path reaches tt_face_load_svg_doc, which trusts the gzip trailer's ISIZE and requests an uncapped 128 MiB buffer via FT_QALLOC), and post_benign reports large_alloc_count=0 again (the companion fix caps the buffer size, matching upstream commit 6fa8725a4167's MAX_SVG_SIZE guard). This is a behavioral/logic oracle (no crash expected or required) measuring an unchecked oversized-allocation request, which is a faithful proxy for the documented allocation-bomb root cause. Same input/command invariant across all three builds.

## Agent oracle

- machine gate: inconclusive (unproven)
- basis: The agent claim lacks a matching admissible three-version oracle.
- bug_marker: "ORACLE library_error=0 face_error=0 size_error=0 glyph_error=0 face_flags=68185 glyph_format=1869968492 large_alloc_count=1 max_large_bytes=134217728 / ORACLE_RESULT=VULNERABLE_128M_ALLOCATION_REQUEST"
- pre_marker: "ORACLE library_error=0 face_error=0 size_error=0 glyph_error=0 face_flags=68185 glyph_format=1869968492 large_alloc_count=0 max_large_bytes=0 / ORACLE_RESULT=NO_LARGE_ALLOCATION_REQUEST"
- benign_marker: "ORACLE library_error=0 face_error=0 size_error=0 glyph_error=0 face_flags=68185 glyph_format=1869968492 large_alloc_count=0 max_large_bytes=0 / ORACLE_RESULT=NO_LARGE_ALLOCATION_REQUEST"
- target execution: run_poc(pre_intro): exit=0, output contains large_alloc_count=0 max_large_bytes=0, ORACLE_RESULT=NO_LARGE_ALLOCATION_REQUEST. run_poc(post_intro): exit=1, output contains large_alloc_count=1 max_large_bytes=134217728, ORACLE_RESULT=VULNERABLE_128M_ALLOCATION_REQUEST. run_poc(post_benign): exit=0, output contains large_alloc_count=0 max_large_bytes=0, ORACLE_RESULT=NO_LARGE_ALLOCATION_REQUEST. All three builds succeeded (build_ok=true) and used the identical input svg-alloc.ttf and identical run.sh/oracle.c invocation.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=f93a897afedf  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=8d7534a1389b7839e79e6adc11826d674316760f35fc77e195a0b935f7468750
  source_integrity=True
  output_tail:
    ORACLE library_error=0 face_error=0 size_error=0 glyph_error=0 face_flags=68185 glyph_format=1869968492 large_alloc_count=0 max_large_bytes=0
    ORACLE_RESULT=NO_LARGE_ALLOCATION_REQUEST
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=1  poc_ran=True  patched=False
  commit=5cf01aa2b267  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=8d7534a1389b7839e79e6adc11826d674316760f35fc77e195a0b935f7468750
  source_integrity=True
  output_tail:
    ORACLE library_error=0 face_error=0 size_error=0 glyph_error=0 face_flags=68185 glyph_format=1869968492 large_alloc_count=1 max_large_bytes=134217728
    ORACLE_RESULT=VULNERABLE_128M_ALLOCATION_REQUEST
    VERIFY_EXIT=1
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=f93a897afedf  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=8d7534a1389b7839e79e6adc11826d674316760f35fc77e195a0b935f7468750
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    ORACLE library_error=0 face_error=0 size_error=0 glyph_error=0 face_flags=68185 glyph_format=1869968492 large_alloc_count=0 max_large_bytes=0
    ORACLE_RESULT=NO_LARGE_ALLOCATION_REQUEST
    VERIFY_EXIT=0
```

## Interpretation

The available evidence does not establish both labels. Inspect the findings and per-version results for the limiting reason.
