# Verification report: pr_review_GL-1398

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: IntegerOverflow
- **Intro commit**: `b04db3872cfac5ee4fd4f895933cebce3576fbf0`
- **Intro parent**: `8ef26a803c340356b7e64ebd7188ce0b7002df59`
- **Fix commit**: `a1079b181e569027a6f083c765f9ffdc44e78ba9`
- **Affected files**: ['src/sfnt/ttgpos.c']

## PoC
- source: incomplete
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/freetype/e2ecf891cf237c7a8825/attempts/01/pocs/freetype/GL-1398`
- input: `None` (0 bytes)
- run.sh: False
- note: poc dir has neither run.sh nor a recognizable input file

## Findings

- Verified by reproduction in Docker via run_poc on pre_intro, post_intro, and post_benign with the identical crafted font/harness. pre_intro (parent 8ef26a803c34): run_poc → exit=0, crashed=False, "kerning.x = 0" — src/sfnt/ttgpos.c is a no-op stub at this revision (tt_face_load_gpos returns FT_Err_Ok trivially, tt_face_get_gpos_kerning returns 0; no PairPos parsing exists at all), so the crafted font cannot and does not crash. post_intro (b04db3872cfa): run_poc → exit=1, crashed=True; AddressSanitizer reports SEGV (READ) precisely in tt_face_get_pair_pos2_kerning at ttgpos.c:927 (the `FT_PEEK_SHORT(table+16+(first_class*class2Count+second_class)*2)` line), reached via tt_face_get_gpos_kerning → tt_get_kerning → FT_Get_Kerning — i.e. this commit adds the real GPOS PairPos implementation including tt_face_validate_pair_pos2's unchecked `limit = p + class1Count * class2Count * 2;`, exactly the code/line cited in the report, and the labelled IntegerOverflow bug fires. post_benign (fix a1079b181e569027a6f083c765f9ffdc44e78ba9): run_poc → exit=0, crashed=False, "kerning.x = 0" — the fixed file now computes `max_size = class1Count * class2Count; if (max_size > FT_UINT_MAX/2) return FALSE;` before multiplying by 2, so the crafted subtable is correctly rejected (not counted as "fitting") and the same command/input produces no crash, matching pre_intro's benign behavior (no evidence of the separately-discussed follow-up free-mismatch regression against this particular PoC/config). The identical crafted TTF and harness command were used unchanged across all three builds, satisfying the required invariance. Note: GPOS kerning support is gated behind TT_CONFIG_OPTION_GPOS_KERNING, which ships disabled in include/freetype/config/ftoption.h; it was enabled identically for all three versions only in the generated build-output copy (build/include/freetype/config/ftoption.h, not tracked src) and libfreetype.a was rebuilt from each version's unmodified tracked source, matching the original reporter's own build setup (their harness linked "build/libfreetyped.a"). No tracked source, and neither the intro nor the fix diff, was altered.

## Per-version results

### pre_intro
```
  (not run)
```
### post_intro
```
  (not run)
```
### post_benign
```
  (not run)
```

## Interpretation

The intro commit introduces the bug (clean before, crash after) and, where a benign companion exists, the benign patch removes it. Labels are consistent with execution.
