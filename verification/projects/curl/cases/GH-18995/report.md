# Verification report: pr_review_GH-18995

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: DoubleFree
- **Intro commit**: `06d12105c7aa883a62802e36eebb76d5303247d0`
- **Intro parent**: `a61eac6248ea29e499f7e9dbd1c27661ef58b754`
- **Fix commit**: `bf41be6292cf712315815c722aab2653a0ec827f`
- **Affected files**: ['lib/url.c']

## PoC
- source: agent-generated (initial source: no_poc)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/curl/3b80189c6d3cd1f08b7b/attempts/01/pocs/curl/GH-18995`
- input: `None` (0 bytes)
- run.sh: True

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- Ran the identical /poc/run.sh (same PoC bytes/command) via run_poc on all three configured versions after applying the identical libidn2-enabling build/link additions to each.

post_intro: run_poc reports crashed=True, exit=134, with an AddressSanitizer "attempting double-free" report. First free occurs inside reuse_conn -> conn_free(old_conn) -> Curl_free_idnconverted_hostname (url.c:1649, called from url.c:3561 reuse_conn / url.c:3910 create_conn) when the freshly-created (about to be discarded) connectdata's conn_to_host.encalloc is freed — even though that identical pointer was just shallow-copied onto the kept connection (old_conn->conn_to_host.encalloc was never NULLed, only .rawalloc was, per the task's root-cause description). The second free of the same heap block happens later during the process's normal cleanup (curl_share_cleanup -> Curl_conncache_close_all_connections -> Curl_disconnect -> conn_free -> Curl_free_idnconverted_hostname, url.c:768/873) on the connection that still holds the dangling pointer. This exactly matches the described DoubleFree root cause.

pre_intro: run_poc reports crashed=False, exit=0, normal connection reuse ("Re-using existing connection #0"), no sanitizer report. Source inspection shows pre_intro's reuse_conn discards the template connection with a bare `free(conn)` (not conn_free()), so the shared host/conn_to_host pointers are never walked/freed at that point — this specific double free does not exist yet before the intro commit.

post_benign: run_poc reports crashed=False, exit=0, normal connection reuse, no sanitizer report. The fix commit introduces url_move_hostname(), which does `Curl_free_idnconverted_hostname(dest); *dest = *src; memset(src, 0, sizeof(*src));`, correctly zeroing both rawalloc and encalloc on the source side, eliminating the dangling shared pointer while preserving connection-reuse behavior.

The exact same reproducer command and inputs (/poc/run.sh, unchanged) were used across all three builds; the only difference is the target source revision itself plus the identical, uniformly-applied libidn2-enabling build/link additions.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=a61eac6248ea  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=ca0d25bd53e487995cc816c653d1be4202b0fa1b0ad7162ce682b136d03d1312
  source_integrity=True
  output_tail:
    > Host: orig.example:8099
    > User-Agent: curl/7.83.1-DEV
    > Accept: */*
    > 
    127.0.0.1 - - [29/Sep/2026 21:15:15] "GET / HTTP/1.1" 200 -
    * Mark bundle as not supporting multiuse
    < HTTP/1.1 200 OK
    < Server: SimpleHTTP/0.6 Python/3.10.12
    < Date: Tue, 29 Sep 2026 21:15:15 GMT
    < Content-type: text/html
    < Content-Length: 12
    < Last-Modified: Tue, 29 Sep 2026 21:15:14 GMT
    < 
    { [12 bytes data]
    * Connection #0 to host café.example left intact
    + CURL_EXIT=0
    + kill 11
    + wait 11
    + echo CURL_EXIT=0
    + exit 0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=06d12105c7aa  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=ca0d25bd53e487995cc816c653d1be4202b0fa1b0ad7162ce682b136d03d1312
  source_integrity=True
  sanitizer:
    Length: 12
    < Last-Modified: Tue, 29 Sep 2026 21:15:10 GMT
    < 
    { [12 bytes data]
    * Connection #0 to host café.example left intact
    =================================================================
    ==13==ERROR: AddressSanitizer: attempting double-free on 0x503000020a10 in thread T0:
        #0 0x7f6d00ff8537 in __interceptor_free ../../../../src/libsanitizer/asan/asan_malloc_linux.cpp:127
        #1 0x5606b91935a1 in Curl_free_idnconverted_hostname /work/lib/url.c:1649
        #2 0x5606b9193649 in conn_free /work/lib/url.c:768
        #3 0x5606b91945e2 in Curl_disconnect /work/lib/url.c:873
        #4 0x5606b91c5b12 in Curl_conncache_close_all_connections /work/lib/conncache.c:542
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=a61eac6248ea  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=ca0d25bd53e487995cc816c653d1be4202b0fa1b0ad7162ce682b136d03d1312
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    > Host: orig.example:8099
    > User-Agent: curl/7.83.1-DEV
    > Accept: */*
    > 
    127.0.0.1 - - [29/Sep/2026 21:15:18] "GET / HTTP/1.1" 200 -
    * Mark bundle as not supporting multiuse
    < HTTP/1.1 200 OK
    < Server: SimpleHTTP/0.6 Python/3.10.12
    < Date: Tue, 29 Sep 2026 21:15:18 GMT
    < Content-type: text/html
    < Content-Length: 12
    < Last-Modified: Tue, 29 Sep 2026 21:15:17 GMT
    < 
    { [12 bytes data]
    * Connection #0 to host café.example left intact
    + CURL_EXIT=0
    + kill 11
    + wait 11
    + echo CURL_EXIT=0
    + exit 0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
