# Verification report: pr_review_GH-19438

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: DoubleFree
- **Intro commit**: `cd3be116b688f293376a3071ed1db3130c5139fa`
- **Intro parent**: `76d13c721bcd992e3e19f52d3a5281b8755283f3`
- **Fix commit**: `00872d5c98bf977eff7d4276eb7379c2b3a7eed6`
- **Affected files**: ['lib/curl_rtmp.c']

## PoC
- source: agent-generated (initial source: no_poc)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/curl/99b24738ed1b5fc2159d/attempts/01/pocs/curl/GH-19438`
- input: `rtmp_stub.h` (1184 bytes)
- run.sh: True

## Findings

- This container's curl was configured without librtmp (only the librtmp1 runtime .so.1 is installed, no -dev headers/symlink), so the stock `curl rtmp://...` path never reaches lib/curl_rtmp.c at all (it compiles to an empty TU without USE_LIBRTMP), and no existing PoC input file was usable. To reproduce faithfully, /poc/run.sh #includes the actual, unmodified lib/curl_rtmp.c from whichever revision is built (with -DUSE_LIBRTMP=1 and a minimal stand-in <librtmp/rtmp.h> supplying just the fields/functions curl_rtmp.c references), links against the project's real lib/hash.c object so Curl_conn_meta_set/get/remove exercise the genuine Curl_hash implementation, and drives rtmp_setup_connection() with a URL for which the fake RTMP_SetupURL() reports a parse failure (mirroring the reporter's malformed-RTMP-URL scenario), followed by the connection-teardown path appropriate to that revision. run_poc confirmed on all three builds:

- pre_intro (76d13c721bcd): exit=0, crashed=False. rtmp_setup_connection() manually calls RTMP_Free(r) on the RTMP_SetupURL failure path; conn->proto.rtmp is only assigned on the success path so it stays NULL, and the old-style rtmp_disconnect() teardown sees r==NULL and does nothing further — single free, correct pre-bug behavior.
- post_intro (cd3be116b688): exit=134, crashed=True. rtmp_setup_connection() registers r into conn->meta_hash via Curl_conn_meta_set(..., rtmp_conn_dtor) right after RTMP_Alloc(), but still manually calls RTMP_Free(r) on the RTMP_SetupURL failure path (the pre-existing manual free was not removed when ownership moved to the meta-hash destructor). Tearing the connection down (Curl_hash_destroy, matching real url.c cleanup) runs rtmp_conn_dtor(), which calls RTMP_Free(r) again on the same pointer. AddressSanitizer reports a double-free with the exact expected stack: freed first at curl_rtmp.c:245 (rtmp_setup_connection's manual free) and freed again at curl_rtmp.c:231 (rtmp_conn_dtor via Curl_hash_destroy/hash_elem_destroy) — matching the meta.json root cause precisely.
- post_benign (fix on top of 76d13c721bcd): exit=0, crashed=False. The manual RTMP_Free(r) on the failure path is removed (comment: "rtmp_conn_dtor() performs the cleanup"), relying solely on the meta-hash destructor; RTMP_Free is called exactly once, no crash.

Same triggering scenario (RTMP_SetupURL failure during connection setup) reproduced across all three revisions confirms intro introduces the double-free and the benign/fix revision removes it.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=76d13c721bcd  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=f96bd65839f7fcde58267e0f1e04cfd4c73158456707a4eaa6fcfae03df5a146
  source_integrity=True
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=cd3be116b688  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=f96bd65839f7fcde58267e0f1e04cfd4c73158456707a4eaa6fcfae03df5a146
  source_integrity=True
  sanitizer:
    eturned
    [harness] tearing down conn->meta_hash (invokes rtmp_conn_dtor if 'r' is still registered)...
    [harness] RTMP_Free() call
    =================================================================
    ==8==ERROR: AddressSanitizer: attempting double-free on 0x503000000070 in thread T0:
        #0 0x7ff894e75537 in __interceptor_free ../../../../src/libsanitizer/asan/asan_malloc_linux.cpp:127
        #1 0x55e1406f161f in RTMP_Free /poc/harness_postintro.c:66
        #2 0x55e1406f164d in rtmp_conn_dtor curl_rtmp.c:231
        #3 0x55e1406f246b in hash_elem_clear_ptr /work/lib/hash.c:137
        #4 0x55e1406f255a in hash_elem_destroy /work/lib/hash.c:147
        #5 0x55e1406f329f in Curl_hash_clean /work/lib/hash.c:302
        #6 0x55e1406f338f in Curl_hash_destroy /work/lib/hash.c:280
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=76d13c721bcd  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=f96bd65839f7fcde58267e0f1e04cfd4c73158456707a4eaa6fcfae03df5a146
  source_integrity=True
  patch_method=plain  patch_clean=True
```

## Interpretation

The intro commit introduces the bug (clean before, crash after) and, where a benign companion exists, the benign patch removes it. Labels are consistent with execution.
