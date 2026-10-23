# Verification report: pr_review_GH-18457

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: UseAfterFree
- **Intro commit**: `be39ed19a5124a900626ab377e2afe5f41839830`
- **Intro parent**: `91d451b48809f20415ba8627786f5d4f5aaf8bfe`
- **Fix commit**: `c278c508e2acfad5f2603febfdba80a30427cd3f`
- **Affected files**: ['lib/http.c']

## PoC
- source: locally_fix_derived
- dir: `/research-data/secprbench/curl-gh18457-verification-unified29-v1/cases/curl/ce51eef11889909a7d37/attempts/01/pocs/curl/GH-18457`
- input: `remote-cookie.poc` (196 bytes)
- run.sh: True

## Findings

- No anomalies from deterministic checks.

## Per-version results

### pre_intro
```
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=91d451b48809  note=
```
### post_intro
```
  build_ok=True  crashed=True  exit=1  poc_ran=True  patched=False
  commit=be39ed19a512  note=
  sanitizer:
    AIN_COOKIE_UNLOCK=1
    MAIN_COOKIE_UNLOCK=2
    MAIN_COOKIE_UNLOCK=3
    REPLACE_RESULT=0 HTTP=200
    REPLACE_COMPLETED_BEFORE_MAIN_CONTINUES
    =================================================================
    ==17==ERROR: AddressSanitizer: heap-use-after-free on address 0x50c000000428 at pc 0x5591f161aac7 bp 0x7fff7381bc30 sp 0x7fff7381bc20
    READ of size 8 at 0x50c000000428 thread T0
        #0 0x5591f161aac6 in Curl_node_elem /work/lib/llist.c:236
        #1 0x5591f173fad0 in Curl_http_cookies /work/lib/http.c:2274
        #2 0x5591f1741e66 in Curl_http /work/lib/http.c:2698
        #3 0x5591f16391d8 in multi_do /work/lib/multi.c:1633
```
### post_benign
```
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=91d451b48809  note=
  patch_method=plain  patch_clean=True
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
