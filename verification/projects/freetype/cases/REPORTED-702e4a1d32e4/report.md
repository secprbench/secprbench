# Verification report: pr_review_REPORTED-702e4a1d32e4

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: BufferOverflow
- **Intro commit**: `582de1a4b6f6269bdb358605f9b23406988cd5b5`
- **Intro parent**: `fd92af79d801880faf070c84d0c274081369eb76`
- **Fix commit**: `702e4a1d32e4b911e85cc7df84b3ba395c28dab3`
- **Affected files**: ['src/truetype/ttgxvar.c']

## PoC
- source: poc-watch
- dir: `/research-data/secprbench/season100-balanced-20261001/verification-v3/cases/freetype/c86466d69ddc039c06d4/attempts/01/pocs/freetype/REPORTED-702e4a1d32e4`
- input: `controlled_gvar_256axis.ttf` (796580 bytes)
- run.sh: False

## Findings

- No anomalies from deterministic checks.

## Per-version results

### pre_intro
```
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=fd92af79d801  note=
```
### post_intro
```
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=582de1a4b6f6  note=
  sanitizer:
    VERIFY_EXIT=134
    
    =================================================================
    ==8==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x61a0000e2d08 at pc 0x5653865e51df bp 0x7ffde8e431b0 sp 0x7ffde8e431a8
    WRITE of size 8 at 0x61a0000e2d08 thread T0
        #0 0x5653865e51de in TT_Vary_Apply_Glyph_Deltas /work/src/truetype/ttgxvar.c:4216:26
        #1 0x5653865e590e in TT_Process_Simple_Glyph /work/src/truetype/ttgload.c:905:15
        #2 0x5653865d9f2e in load_truetype_glyph /work/src/truetype/ttgload.c:1652:15
        #3 0x5653865a3531 in TT_Load_Glyph /work/src/truetype/ttgload.c:2621:13
        #4 0x5653865a3531 in tt_glyph_load /work/src/truetype/ttdriver.c:502:13
        #5 0x56538645a456 in FT_Load_Glyph /work/src/base/ftobjs.c:1066:15
        #6 0x565386458a78 in exercise_face /work/harness.c:90:13
```
### post_benign
```
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=fd92af79d801  note=
  patch_method=plain  patch_clean=True
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
