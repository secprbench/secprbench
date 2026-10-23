# Verification report: pr_review_GH-28216

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: LogicError
- **Intro commit**: `3d254b31344e82b8f10fda8bab196757a377eb63`
- **Intro parent**: `643f542a89bee93e043d0899b2a1ca700d1cc418`
- **Fix commit**: `c0527256d2e6a148931e1d8b9b0ff4af7564caae`
- **Affected files**: ['crypto/encode_decode/decoder_pkey.c']

## PoC
- source: agent-generated (initial source: no_poc)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/openssl/dd55af30b4b514a3ca2f/attempts/02/pocs/openssl/GH-28216`
- input: `None` (0 bytes)
- run.sh: False
- note: poc dir has neither run.sh nor a recognizable input file

## Findings

- Exact bug and unaffected output lines matched the shared three-version Docker replay.
- Root cause confirmed by source diff and by a targeted, self-checking dynamic PoC. The PoC forces the specific allocation performed inside lh_DECODER_CACHE_ENTRY_insert() to fail (via a malloc hook matched by exact call-site file:line, touching no other allocation), driving OSSL_DECODER_CTX_new_for_pkey() into the intro commit's newly-added error branch while cache->lock is held for write. A subsequent, ordinary call to the same API (no induced failure) serves as the oracle: it must succeed promptly if the lock was released. Running the identical sequence against all three built revisions (3 repetitions each, fully reproducible) gives a clean 3-way split: pre_intro never reaches the buggy branch at all (no error handling on insert failure existed) and the lock is always released, so the probe call always succeeds; post_intro takes the new error branch, leaks cache->lock, and the probe call fails every time (fast failure rather than a hang, matching the original reporter's account of an EBUSY-style same-thread re-lock failure); post_benign takes the same error branch but its added CRYPTO_THREAD_unlock() releases the lock, so the probe call succeeds every time, exactly matching the fix commit message ("never unlocked a write lock we were holding ... Fix it by ensuring the lock is released in the error path"). intro_verified=yes and benign_verified=yes with high confidence.

## Agent oracle

- machine gate: verified (behavioral)
- basis: Exact bug and unaffected output lines matched the shared three-version Docker replay.
- bug_marker: "[poc] RESULT: PROBE_FAIL (probe call returned NULL although no failure was induced for it; consistent with a leaked cache->lock causing the write-lock re-acquisition to fail)"
- pre_marker: "[poc] RESULT: PROBE_OK (probe call returned a valid ctx promptly; cache->lock was correctly released)"
- benign_marker: "[poc] RESULT: PROBE_OK (probe call returned a valid ctx promptly; cache->lock was correctly released)"
- target execution: Source diff: post_intro (3d254b31344e) added in OSSL_DECODER_CTX_new_for_pkey() (crypto/encode_decode/decoder_pkey.c), after CRYPTO_THREAD_write_lock(cache->lock) and lh_DECODER_CACHE_ENTRY_insert(): `if (lh_DECODER_CACHE_ENTRY_error(cache->hashtable)) { ctx = NULL; ERR_raise(...); goto err; }`, and the shared `err:` label never calls CRYPTO_THREAD_unlock(cache->lock) (only decoder_cache_entry_free()/OSSL_DECODER_CTX_free()) -- a genuine lock leak, unlike every earlier goto-err site in the function which precedes the lock acquisition. post_benign (fix tree, same as parent 643f542a89be) inserts `CRYPTO_THREAD_unlock(cache->lock);` immediately before that ERR_raise/goto err. pre_intro (643f542a89be) lacks this check/branch entirely; insert failures are silently ignored and the lock is always released at the function's normal unlock. Dynamic evidence: identical 3-call PoC sequence, run 3x per version under ASan/UBSan. post_intro: triggering call returns NULL (error branch taken); probe call (no induced failure) also returns NULL every time, with libcrypto error queue pointing at decoder_pkey.c:847/765 -- consistent with the still-held write lock causing the re-lock attempt to fail, matching the reporter's own description of an EBUSY/assert on re-locking in the same thread. pre_intro: triggering call returns non-NULL (insert failure silently ignored, since the check doesn't exist yet); probe call succeeds every time. post_benign: triggering call returns NULL (same error handling as post_intro) but probe call succeeds every time (lock correctly released by the added unlock call).

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=643f542a89be  note=build cached
  command=cd /tmp && cc -O0 -g -fsanitize=address,undefined -pthread -I/work/include -o poc /poc/poc.c /work/libcrypto.a -ldl && for i in 1 2 3; do timeout 15 ./poc; echo "EXIT=$?"; done
  poc_sha256=6aee8a8b67a9805cb648cdfe6b4252430a590e3c3da9f65d657566e42ced0de5
  source_integrity=True
  output_tail:
    XIT=0
    VERIFY_EXIT=0
    
    [poc] warm-up call returned 0x50b000002400
    [poc] forcing malloc failure at crypto/lhash/lhash.c:114 (hit #1)
    [poc] triggering call returned 0x50b000002610, hit_count=1, fail_done=1
    [poc] triggering call succeeded despite forced allocation failure (insert error not checked by this revision)
    [poc] RESULT: PROBE_OK (probe call returned a valid ctx promptly; cache->lock was correctly released)
    [poc] warm-up call returned 0x50b000002400
    [poc] forcing malloc failure at crypto/lhash/lhash.c:114 (hit #1)
    [poc] triggering call returned 0x50b000002610, hit_count=1, fail_done=1
    [poc] triggering call succeeded despite forced allocation failure (insert error not checked by this revision)
    [poc] RESULT: PROBE_OK (probe call returned a valid ctx promptly; cache->lock was correctly released)
    [poc] warm-up call returned 0x50b000002400
    [poc] forcing malloc failure at crypto/lhash/lhash.c:114 (hit #1)
    [poc] triggering call returned 0x50b000002610, hit_count=1, fail_done=1
    [poc] triggering call succeeded despite forced allocation failure (insert error not checked by this revision)
    [poc] RESULT: PROBE_OK (probe call returned a valid ctx promptly; cache->lock was correctly released)
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=3d254b31344e  note=build cached
  command=cd /tmp && cc -O0 -g -fsanitize=address,undefined -pthread -I/work/include -o poc /poc/poc.c /work/libcrypto.a -ldl && for i in 1 2 3; do timeout 15 ./poc; echo "EXIT=$?"; done
  poc_sha256=6aee8a8b67a9805cb648cdfe6b4252430a590e3c3da9f65d657566e42ced0de5
  source_integrity=True
  output_tail:
    ->lock causing the write-lock re-acquisition to fail)
    0048C769EF7F0000:error:078C0100:common libcrypto routines::malloc failure:crypto/lhash/lhash.c:114:
    0048C769EF7F0000:error:1E08000F:DECODER routines:OSSL_DECODER_CTX_new_for_pkey:CRYPTO lib:crypto/encode_decode/decoder_pkey.c:847:
    0048C769EF7F0000:error:1E08000F:DECODER routines:OSSL_DECODER_CTX_new_for_pkey:CRYPTO lib:crypto/encode_decode/decoder_pkey.c:765:
    [poc] warm-up call returned 0x50b000002400
    [poc] forcing malloc failure at crypto/lhash/lhash.c:114 (hit #1)
    [poc] triggering call returned (nil), hit_count=1, fail_done=1
    [poc] triggering call failed as expected (insert error path checked/taken)
    [poc] RESULT: PROBE_FAIL (probe call returned NULL although no failure was induced for it; consistent with a leaked cache->lock causing the write-lock re-acquisition to fail)
    00687CBCAA7F0000:error:078C0100:common libcrypto routines::malloc failure:crypto/lhash/lhash.c:114:
    00687CBCAA7F0000:error:1E08000F:DECODER routines:OSSL_DECODER_CTX_new_for_pkey:CRYPTO lib:crypto/encode_decode/decoder_pkey.c:847:
    00687CBCAA7F0000:error:1E08000F:DECODER routines:OSSL_DECODER_CTX_new_for_pkey:CRYPTO lib:crypto/encode_decode/decoder_pkey.c:765:
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=643f542a89be  note=build cached
  command=cd /tmp && cc -O0 -g -fsanitize=address,undefined -pthread -I/work/include -o poc /poc/poc.c /work/libcrypto.a -ldl && for i in 1 2 3; do timeout 15 ./poc; echo "EXIT=$?"; done
  poc_sha256=6aee8a8b67a9805cb648cdfe6b4252430a590e3c3da9f65d657566e42ced0de5
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    EXIT=0
    EXIT=0
    EXIT=0
    VERIFY_EXIT=0
    
    [poc] warm-up call returned 0x50b000002400
    [poc] forcing malloc failure at crypto/lhash/lhash.c:114 (hit #1)
    [poc] triggering call returned (nil), hit_count=1, fail_done=1
    [poc] triggering call failed as expected (insert error path checked/taken)
    [poc] RESULT: PROBE_OK (probe call returned a valid ctx promptly; cache->lock was correctly released)
    [poc] warm-up call returned 0x50b000002400
    [poc] forcing malloc failure at crypto/lhash/lhash.c:114 (hit #1)
    [poc] triggering call returned (nil), hit_count=1, fail_done=1
    [poc] triggering call failed as expected (insert error path checked/taken)
    [poc] RESULT: PROBE_OK (probe call returned a valid ctx promptly; cache->lock was correctly released)
    [poc] warm-up call returned 0x50b000002400
    [poc] forcing malloc failure at crypto/lhash/lhash.c:114 (hit #1)
    [poc] triggering call returned (nil), hit_count=1, fail_done=1
    [poc] triggering call failed as expected (insert error path checked/taken)
    [poc] RESULT: PROBE_OK (probe call returned a valid ctx promptly; cache->lock was correctly released)
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
