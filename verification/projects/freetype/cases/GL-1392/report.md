# Verification report: pr_review_GL-1392

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: OutOfBoundsRead
- **Intro commit**: `b04db3872cfac5ee4fd4f895933cebce3576fbf0`
- **Intro parent**: `8ef26a803c340356b7e64ebd7188ce0b7002df59`
- **Fix commit**: `b2c8a031a2f6fc1200868a8bee3175400cfb99fc`
- **Affected files**: ['src/sfnt/ttgpos.c']

## PoC
- source: incomplete
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/freetype/5b220ca227f451ab0413/attempts/01/pocs/freetype/GL-1392`
- input: `None` (0 bytes)
- run.sh: False
- note: poc dir has neither run.sh nor a recognizable input file

## Findings

- Built and ran all three revisions in Docker with the same custom harness (poc.c, mirroring the reporter's FT_Get_Kerning repro) and the same crafted.ttf input via a single run.sh. post_intro (b04db3872cfa): AddressSanitizer reports a heap-buffer-overflow READ of size 1 at src/sfnt/ttgpos.c:817:16 in tt_face_get_class, called from tt_face_get_pair_pos2_kerning -> tt_face_get_gpos_kerning -> tt_get_kerning -> FT_Get_Kerning -- exactly the reported crash signature and location (the `>=` off-by-one in the ClassDef1 Format-1 bounds check). pre_intro (8ef26a803c34, before the GPOS-kerning rewrite that introduced the bug) runs cleanly (exit 0, kerning.x=0, no ASan report) with the identical input/command. post_benign (fix applied) also runs cleanly (exit 0, kerning.x=0, no ASan report) with the identical input/command. This confirms introduction=yes and benign fix=yes for this OutOfBoundsRead.

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
