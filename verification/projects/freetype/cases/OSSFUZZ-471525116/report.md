# Verification report: pr_review_OSSFUZZ-471525116

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: IntegerOverflow
- **Intro commit**: `771449f14a35afa324cbf089f569e915ac9501ed`
- **Intro parent**: `7099b09e9629d8ea39231520739b4b6d90691d0c`
- **Fix commit**: `7b72c0f238ff00ede4a74e7d283d233d1c0bafca`
- **Affected files**: ['src/autofit/aflatin.c']

## PoC
- source: no_poc
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/freetype/ee0b0fd6b9d4f7f28d19/attempts/01/pocs/freetype/OSSFUZZ-471525116`
- input: `None` (0 bytes)
- run.sh: False
- note: poc dir has neither run.sh nor a recognizable input file

## Findings

- Built and ran pre_intro (7099b09e9629), post_intro (771449f14a35) and post_benign (7099b09e9629 + fix) in Docker with the project's ASan+UBSan build. The freetype fuzzer harness's fixed pixel sizes (16/72) never reach the vulnerable code with enough magnitude, and the bug also requires (a) the target glyph's codepoint to be in the autofit "tilde correction" adjustment database (only U+0168/U+0169 qualify), (b) the font to supply usable "blue zone" reference glyphs (else the whole Latin autofit style is disabled), and (c) every one of the ~130 adjustment-database codepoints to resolve via cmap (otherwise an unrelated pre-existing OOB in af_reverse_character_map_new fires first) — none of which the stock harness or its default sizes provide, so no existing/default PoC could reach it. I reverse-engineered af_latin_stretch_tilde's exact wiggle-detection condition (an on-curve point flanked by two off-curve control points sharing its y, both further on-curve neighbors on the same side) from source, and hand-built a minimal SFNT font plus a small custom FT harness (compiled and run against the library under test with the same sanitizer flags as the canonical build) to drive height=max_y-min_y to ~6.19e9 and target_height within 64 units of it. Same font/command across all three builds: pre_intro exits cleanly (0, no crash), post_intro aborts (exit 134) with 'UndefinedBehaviorSanitizer: undefined-behavior /work/src/autofit/aflatin.c:3035:34 ... signed integer overflow: 1490304752 * 6192402018 cannot be represented in type long' inside af_latin_stretch_tilde <- af_latin_hints_apply <- af_autofitter_load_glyph, exactly matching the labelled root cause and the oss-fuzz crash state (af_latin_stretch_bottom_tilde/af_latin_hints_apply/af_autofitter_load_glyph); post_benign (fix applied) again exits cleanly (0, no crash). This cleanly confirms introduction by the intro commit and remediation by the benign/fix commit.

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
