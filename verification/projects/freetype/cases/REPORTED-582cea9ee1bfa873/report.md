# Verification report: pr_review_REPORTED-582cea9ee1bfa873

- **Status**: `inconclusive`
- **Intro verified**: None
- **Benign verified**: None
- **Bug type**: OutOfBoundsRead
- **Intro commit**: `6a982bde85eaef0ed0aee7dabfb9ebc5080c0f36`
- **Intro parent**: `9e8b642b1005a8a16f39113f42b5f75b4518a5a6`
- **Fix commit**: `582cea9ee1bfa87344792c5c54657250e9983138`
- **Affected files**: ['src/autofit/afadjust.c', 'src/autofit/afglobal.h', 'src/autofit/afgsub.c']

## PoC
- source: no_poc
- dir: `/research-data/secprbench/season100-balanced-20261001/verification-v2/cases/freetype/e625dad20e6fc5bb39d1/attempts/01/pocs/freetype/REPORTED-582cea9ee1bfa873`
- input: `None` (0 bytes)
- run.sh: False
- note: poc dir has neither run.sh nor a recognizable input file

## Findings

- The agent claim lacks a matching admissible three-version oracle.
- The labelled bug lives in af_reverse_character_map_new's HarfBuzz-based GSUB-lookup iteration (afadjust.c lines ~1357-1504, confirmed by `grep -n ifdef/endif`), and the whole file afgsub.c (which defines af_parse_gsub / gsub_lookups_single_alternate) is wrapped end-to-end in `#ifdef FT_CONFIG_OPTION_USE_HARFBUZZ ... #endif`. In this benchmark's Docker build for all three revisions (pre_intro 9e8b642b1005, post_intro 6a982bde85ea, post_benign), `/work/include/freetype/config/ftoption.h` has `/* #define FT_CONFIG_OPTION_USE_HARFBUZZ */` commented out, `pkg-config --exists harfbuzz` reports NOTFOUND, no system libharfbuzz-dev package is installed (apt-get install fails with a permission error, so it cannot be added), and `nm` on the built static `libfreetype.a` shows zero `hb_*` symbols and no `af_parse_gsub`/`af_reverse_character_map_new`'s GSUB block compiled in. I verified this identically in pre_intro and post_intro (and the libfreetype.a build artifacts are produced the same way for post_benign). Since HarfBuzz support is not compiled into the autofit module in any of the three built revisions, the array `globals->gsub_lookups_single_alternate[]` and the unchecked `hb_set_next()`-returned index that the fix commit bounds-checks are simply never reached — the reverse-character-map function's HarfBuzz block is dead code here, so af_reverse_character_map_new does nothing GSUB-related at all regardless of the font's GSUB contents. I confirmed my crafted PoC does reach af_latin_metrics_init (glyph loads fine under FT_LOAD_FORCE_AUTOHINT, 'T' resolves to glyph 1 via the cmap) and exercises the Latin autofit path, but the specific GSUB-indexing code that the intro/fix commits touch is unreachable in this build configuration. This is a build-environment limitation (missing/undetected HarfBuzz dependency), not evidence about the patch's correctness, and I have no permission to alter the configured build to add the missing dependency (apt lock requires root, and I must not hand-repair the target build). Per the verification guidelines, a build/environment that does not exercise the affected API must be recorded as unknown rather than inferring introduction=no or benign=yes.

## Agent oracle

- machine gate: inconclusive (unproven)
- basis: The agent claim lacks a matching admissible three-version oracle.

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

The available evidence does not establish both labels. Inspect the findings and per-version results for the limiting reason.
