# Verification report: pr_review_OSSFUZZ-424613326

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: OutOfBoundsRead
- **Intro commit**: `5a07f41d0eddddcae927957c6434c4174bae4e6a`
- **Intro parent**: `3aeabbf87d858398aeee6397cea568e624f38366`
- **Fix commit**: `d3668e00da732654b50e4e81f982544ed6e26390`
- **Affected files**: ['src/sfnt/ttload.c', 'src/sfnt/sfobjs.c']

## PoC
- source: locally_fix_derived
- dir: `/research-data/secprbench/freetype-dfont-paper-pair-import-v1/verification/cases/freetype/67d0bb59828d724deb71/attempts/01/pocs/freetype/OSSFUZZ-424613326`
- input: `two-sfnt.bin` (1775616 bytes)
- run.sh: True

## Findings

- No anomalies from deterministic checks.

## Per-version results

### pre_intro
```
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=3aeabbf87d85  note=
```
### post_intro
```
  build_ok=True  crashed=True  exit=1  poc_ran=True  patched=False
  commit=5a07f41d0edd  note=
  sanitizer:
    VERIFY_EXIT=1
    
    =================================================================
    ==8==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x6020000000b8 at pc 0x5587e0337a46 bp 0x7ffcbf5269d0 sp 0x7ffcbf5269c8
    READ of size 8 at 0x6020000000b8 thread T0
        #0 0x5587e0337a45 in tt_face_load_any /work/src/sfnt/ttload.c:589:17
        #1 0x5587e0360d88 in sfnt_load_table /work/src/sfnt/sfdriver.c:96:12
        #2 0x5587e0247e0f in FT_Load_Sfnt_Table /work/src/base/ftobjs.c:4398:12
        #3 0x5587e02301f2 in main /poc/oracle.c:28:11
        #4 0x7f343cb63d8f in __libc_start_call_main csu/../sysdeps/nptl/libc_start_call_main.h:58:16
        #5 0x7f343cb63e3f in __libc_start_main csu/../csu/libc-start.c:392:3
        #6 0x5587e01723b4 in _start (/work/dfont_directory_oracle+0x1483b4) (BuildId: abc3ac41b3a8cd76a0531daa82ec110f26e0ce8b)
```
### post_benign
```
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=3aeabbf87d85  note=
  patch_method=plain  patch_clean=True
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
