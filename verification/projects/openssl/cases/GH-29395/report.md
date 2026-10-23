# Verification report: pr_review_GH-29395

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: NullPointerDereference
- **Intro commit**: `1a91fda1839bc745e8359f82d19a5ef44ca36f7e`
- **Intro parent**: `8c110311fd5e7f04e2c152b17d44acfd4a279ea6`
- **Fix commit**: `380ff1448596926fc9d252c8e4c2720b006ef912`
- **Affected files**: ['crypto/bio/bio_lib.c']

## PoC
- source: agent-generated (initial source: no_poc)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/openssl/58ae2f7ad3214e64ed74/attempts/01/pocs/openssl/GH-29395`
- input: `None` (0 bytes)
- run.sh: True

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- Built pre_intro (8c110311fd5e), post_intro (1a91fda1839b) and post_benign (fix-equivalent) with OpenSSL's default ASan+UBSan config and ran the identical PoC/run.sh against all three. post_intro crashes with a UBSan 'load of null pointer of type size_t' report at crypto/bio/bio_lib.c:66 inside bio_call_callback, called from BIO_sendmmsg at bio_lib.c:435 (the BIO_CB_SENDMMSG|BIO_CB_RETURN invocation that passes inret=ret (a positive value) but processed=NULL). pre_intro does not crash: BIO_sendmmsg's RETURN callback previously hard-coded inret=0, so the `inret > 0` guard at line 66 was never true and *processed was never dereferenced (dead-safe code path) -- the PoC completes and reports 'BIO_sendmmsg returned 0, processed=0', consistent with the old always-0 inret. post_benign (which passes the real msgs_processed pointer instead of NULL, matching the upstream fix 380ff1448596) also completes without any sanitizer report and shows the *correct* behavior restored: 'BIO_sendmmsg returned 1, processed=1'. This exactly matches meta.json's root cause: 1a91fda1839b changed the previously-safe hardcoded-0 inret to the genuine positive return value while still passing a NULL processed pointer, re-activating a dead code path with an invalid argument; the fix supplies the valid processed pointer. Same reproducer (identical poc.c/run.sh) used unmodified across all three builds.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=8c110311fd5e  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=d7fd92ad577ea3b85d88bb1d710b6537011931ad0f7c8ab946d50be78f8dcc93
  source_integrity=True
  output_tail:
    NO_CRASH: completed successfully
    VERIFY_EXIT=0
    
    legacy_cb called: oper=8 ret=0
    BIO_sendmmsg returned 0, processed=0
    legacy_cb called: oper=1 ret=1
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=1  poc_ran=True  patched=False
  commit=1a91fda1839b  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=d7fd92ad577ea3b85d88bb1d710b6537011931ad0f7c8ab946d50be78f8dcc93
  source_integrity=True
  sanitizer:
    VERIFY_EXIT=1
    
    legacy_cb called: oper=8 ret=1
    crypto/bio/bio_lib.c:66:13: runtime error: load of null pointer of type 'size_t' (aka 'unsigned long')
        #0 0x559580ea4d9a in bio_call_callback /work/crypto/bio/bio_lib.c:66
        #1 0x559580ea64d4 in BIO_sendmmsg /work/crypto/bio/bio_lib.c:435
        #2 0x559580ea457a in main /poc/poc.c:76
        #3 0x7f4507825d8f in __libc_start_call_main ../sysdeps/nptl/libc_start_call_main.h:58
        #4 0x7f4507825e3f in __libc_start_main_impl ../csu/libc-start.c:392
        #5 0x559580ea4024 in _start (/tmp/poc+0x386024)
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=8c110311fd5e  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=d7fd92ad577ea3b85d88bb1d710b6537011931ad0f7c8ab946d50be78f8dcc93
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    NO_CRASH: completed successfully
    VERIFY_EXIT=0
    
    legacy_cb called: oper=8 ret=1
    legacy_cb called: oper=136 ret=1
    BIO_sendmmsg returned 1, processed=1
    legacy_cb called: oper=1 ret=1
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
