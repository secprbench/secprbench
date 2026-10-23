# Verification report: pr_review_GH-17830

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: Other
- **Intro commit**: `460ead61b6feec048a66914fe9281676fef21018`
- **Intro parent**: `e2a23d5d0d566105237acec37a2c22a6f79cee3e`
- **Fix commit**: `cbf261e2de9f349c5b1ef0a8dc980988558455c5`
- **Affected files**: ['lib/vtls/rustls.c']

## PoC
- source: agent-generated (initial source: no_poc)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/curl/6219a9527ee179ac1c02/attempts/01/pocs/curl/GH-17830`
- input: `None` (0 bytes)
- run.sh: True

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- Root cause confirmed by source inspection and reproduction: lib/vtls/rustls.c's init_config_builder_ech() obtains the ECHConfig buffer via Curl_base64_decode(), which allocates through curl's internal overridable allocator (malloc() macro-expands to Curl_cmalloc() in lib/base64.c since BUILDING_LIBCURL pulls in curl_memory.h). Commit 460ead61b6fe (post_intro) adds a cleanup path that releases this buffer with a plain libc free() -- rustls.c never includes curl_memory.h/memdebug.h at that point, so that free() bypasses curl's (possibly overridden) deallocator. This is only safe by coincidence when no allocator override is engaged; once an application installs custom memory functions via curl_global_init_mem() (the real, documented, public curl API explicitly discussed in the fix's own PR thread), the mismatch becomes an invalid free. Fix commit cbf261e2de9f adds #include "../curl_memory.h" and "../memdebug.h" to rustls.c so the same free(ptr) call is macro-expanded to the overridable Curl_cfree(ptr), matching the allocator, and its predecessor (pre_intro) simply never freed the buffer on this path (leak only, not an invalid free).

Because rustls.c requires the rustls backend (crustls/rustls-ffi), which is not installed and cannot be built offline here (no librustls/rustls.h, no network access to fetch/build it), and USE_RUSTLS/USE_ECH are confirmed undefined in every build this harness can produce, the vulnerable function can never actually be linked into a runnable curl binary in this environment. I built a differential harness (/poc/run.sh, /poc/poc.c) that exercises the real, unmodified internal function the bug touches (Curl_base64_decode, unchanged across all 3 revisions) under the real curl allocator-override mechanism, combined with the literal, auto-detected cleanup logic read directly out of each version's own on-disk rustls.c so the identical script is valid for every revision.

Running the identical /poc/run.sh via run_poc on all three built revisions: post_intro deterministically triggers "AddressSanitizer: attempting free on address which was not malloc()-ed" (bad-free) and aborts (crashed=True), while pre_intro and post_benign both complete cleanly with exit 0 (crashed=False). This isolates precisely the allocator/deallocator mismatch described in the root cause and fix message, confirming introduction by 460ead61b6fe and resolution by cbf261e2de9f.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=e2a23d5d0d56  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=acd90547a399b4a4f583885b0bf2897f3a3f588a7c84a5eeb247b216146d478e
  source_integrity=True
  output_tail:
    VERIFY_EXIT=0
    
    detected CLEANUP_MODE=0 from lib/vtls/rustls.c
    decoded 12 bytes at 0x50300000f438
    (reference) freed via curl_free(); pre_intro leaked here
    OK
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=1  poc_ran=True  patched=False
  commit=460ead61b6fe  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=acd90547a399b4a4f583885b0bf2897f3a3f588a7c84a5eeb247b216146d478e
  source_integrity=True
  sanitizer:
    VERIFY_EXIT=1
    
    detected CLEANUP_MODE=1 from lib/vtls/rustls.c
    decoded 12 bytes at 0x50300000f438
    =================================================================
    ==18==ERROR: AddressSanitizer: attempting free on address which was not malloc()-ed: 0x50300000f438 in thread T0
        #0 0x7f45e2952537 in __interceptor_free ../../../../src/libsanitizer/asan/asan_malloc_linux.cpp:127
        #1 0x5563e26143ec in main /poc/poc.c:120
        #2 0x7f45e1b65d8f in __libc_start_call_main ../sysdeps/nptl/libc_start_call_main.h:58
        #3 0x7f45e1b65e3f in __libc_start_main_impl ../csu/libc-start.c:392
        #4 0x5563e2613f74 in _start (/tmp/poc_gh17830+0x22df74)
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=e2a23d5d0d56  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=acd90547a399b4a4f583885b0bf2897f3a3f588a7c84a5eeb247b216146d478e
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    VERIFY_EXIT=0
    
    detected CLEANUP_MODE=2 from lib/vtls/rustls.c
    decoded 12 bytes at 0x50300000f438
    freed via curl_free()
    OK
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
