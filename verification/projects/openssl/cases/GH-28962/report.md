# Verification report: pr_review_GH-28962

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: OutOfBoundsRead
- **Intro commit**: `3c963394d0c7dad0bffdbc452f2c5354355a9720`
- **Intro parent**: `48a2d1e448d48533c88d8b4087ce201d8b33e265`
- **Fix commit**: `dfc6f643c09aba831d4856597ef9633dda2fb6c4`
- **Affected files**: ['crypto/x509/x509_vfy.c']

## PoC
- source: agent-generated (initial source: no_poc)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/openssl/491a3d86cd649fabcbe9/attempts/02/pocs/openssl/GH-28962`
- input: `None` (0 bytes)
- run.sh: True

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- meta.json/discussion.md: intro commit 3c963394d0c7 (parent 48a2d1e448d4) added a "99991231235959Z" no-expiry special case to ossl_x509_check_cert_time() in crypto/x509/x509_vfy.c that calls strcmp() on the raw ASN1_STRING_get0_data() buffer of the notAfter field, which is not guaranteed to be NUL-terminated. Upstream fix dfc6f643c09a (mirrored by post_benign) replaces this with an explicit length check (`notafter->length == 15`) plus memcmp(). Source diff confirms: pre_intro has none of this special-case code at all; post_intro has the strcmp version; post_benign has the length-checked memcmp version. Because normal DER-parsed X.509 certs are always NUL-terminated in this non-fuzzing build configuration (no-fuzz-libfuzzer/no-fuzz-afl; ASN1_STRING_set()/asn1_collect() both append a NUL byte unless FUZZING_BUILD_MODE_UNSAFE_FOR_PRODUCTION is defined), no ordinary certificate-parsing path can supply a non-NUL-terminated buffer here, matching the upstream report title "heap-buffer-overflow in CI fuzzing tests". I therefore built a minimal harness that calls the internal function directly with a controlled ASN1_STRING (via the public ASN1_STRING_set0() API) holding an exactly-sized, non-NUL-terminated buffer that is a genuine prefix of the magic string (so strcmp does not mismatch before running off the end of the allocation) — this reaches the exact vulnerable line via the real target code path (ossl_x509_check_cert_time), not a source copy or grep. Running the identical run.sh/poc.c through run_poc against all three built revisions: pre_intro exits cleanly (return 0, no crash — code doesn't exist yet), post_intro crashes under AddressSanitizer with "heap-buffer-overflow READ of size 6 ... in __interceptor_strcmp ... in ossl_x509_check_cert_time /work/crypto/x509/x509_vfy.c:2213" (the exact strcmp line added by the intro commit, 0 bytes past a 5-byte CRYPTO_malloc'd region), and post_benign exits cleanly again (return 0) using the length-checked memcmp fix. This satisfies the invariance requirement (identical reproducer across all three revisions) with an unambiguous, target-specific sanitizer report confined to post_intro only.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=48a2d1e448d4  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=37f1cf7ce0eb0568cbcdd82ef6cacadd2bdf185ae8527b9f0803033b4c028db2
  source_integrity=True
  output_tail:
    Calling ossl_x509_check_cert_time...
    ossl_x509_check_cert_time returned 0
    DONE_NO_CRASH
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=3c963394d0c7  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=37f1cf7ce0eb0568cbcdd82ef6cacadd2bdf185ae8527b9f0803033b4c028db2
  source_integrity=True
  sanitizer:
    Calling ossl_x509_check_cert_time...
    VERIFY_EXIT=134
    
    =================================================================
    ==14==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x502000000155 at pc 0x7fa9f09515b3 bp 0x7ffccd905930 sp 0x7ffccd9050d8
    READ of size 6 at 0x502000000155 thread T0
        #0 0x7fa9f09515b2 in __interceptor_strcmp ../../../../src/libsanitizer/sanitizer_common/sanitizer_common_interceptors.inc:466
        #1 0x56091952de8a in ossl_x509_check_cert_time /work/crypto/x509/x509_vfy.c:2213
        #2 0x56091951ce78 in main /poc/poc.c:62
        #3 0x7fa9f008ad8f in __libc_start_call_main ../sysdeps/nptl/libc_start_call_main.h:58
        #4 0x7fa9f008ae3f in __libc_start_main_impl ../csu/libc-start.c:392
        #5 0x56091951cca4 in _start (/tmp/poc+0x43fca4)
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=48a2d1e448d4  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=37f1cf7ce0eb0568cbcdd82ef6cacadd2bdf185ae8527b9f0803033b4c028db2
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    Calling ossl_x509_check_cert_time...
    ossl_x509_check_cert_time returned 0
    DONE_NO_CRASH
    VERIFY_EXIT=0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
