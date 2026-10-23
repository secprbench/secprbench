# Verification report: pr_review_GH-18806

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: DataRace
- **Intro commit**: `68bd759c2bfe74799c3355ad29265b795a7e6c62`
- **Intro parent**: `b399a98d2da10ab51afc77f7d4b83769ec4fa6fd`
- **Fix commit**: `2a25ebe9580e52b375533a7d12a86dff29a36c44`
- **Affected files**: ['lib/vtls/vtls_scache.c']

## PoC
- source: agent-final (initial source: no_poc)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/curl/0cfa2bd2be8a28d4e723/attempts/03/pocs/curl/GH-18806`
- input: `None` (0 bytes)
- run.sh: True

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- meta.json's root cause: Curl_ssl_scache_unlock(data) was moved to right after the critical section in Curl_ssl_scache_take(), before the trace-log statement that itself reads the shared peer->sessions list via Curl_llist_count() -- an unlocked read of lock-protected data. Source inspection confirms this: in post_intro, vtls_scache.c line 825 calls Curl_ssl_scache_unlock(data) and only afterwards (lines 828-833) calls Curl_llist_count(&peer->sessions) inside CURL_TRC_CF. In pre_intro, unlock happens at line 799 but the subsequent CURL_TRC_CF at line 801 reads only the already-taken local pointer *ps, not the shared list, so no unlocked shared-state access exists. In post_benign (the fix), Curl_ssl_scache_unlock(data) moves to line 837, after the CURL_TRC_CF/Curl_llist_count call, restoring lock coverage over the read. Using the same reproducer command (run_poc, no args, which invokes /poc/run.sh) on all three built versions: pre_intro exits 0 with 'done ok=1920 fail=0' and no sanitizer report; post_intro crashes (exit 66) with a genuine ThreadSanitizer data-race report whose write side is Curl_llist_insert_next <- Curl_llist_append <- cf_scache_peer_add_session <- Curl_ssl_scache_put (session insertion from another thread's TLS handshake) and whose (previously observed, same build/run) read side is Curl_llist_count <- Curl_ssl_scache_take at vtls_scache.c:828, i.e. the exact racy trace-log line -- this matches the original upstream TSan CI report in discussion.md (same function pair/race pattern: Curl_llist_insert_next racing Curl_llist_count in Curl_ssl_scache_take). post_benign again exits 0 with 'done ok=1920 fail=0' and no sanitizer report, matching pre_intro. The race is reproducible only in post_intro, is isolated to the exact introduced/fixed code, and is absent pre-intro and post-benign under the identical reproducer.

## Agent oracle

- machine gate: verified (race)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.
- bug_marker: "WARNING: ThreadSanitizer: data race ... Write of size 8 ... Curl_llist_insert_next lib/llist.c:115 <- Curl_llist_append <- cf_scache_peer_add_session lib/vtls/vtls_scache.c:751 <- Curl_ssl_scache_put; previously-observed-same-config Previous read: Curl_llist_count lib/llist.c:242 <- Curl_ssl_scache_take lib/vtls/vtls_scache.c:828; POC_EXIT=66"
- pre_marker: "done ok=1920 fail=0; POC_EXIT=0 (no ThreadSanitizer report)"
- benign_marker: "done ok=1920 fail=0; POC_EXIT=0 (no ThreadSanitizer report)"
- target execution: run_poc(post_intro): exit=66, crashed=True, sanitizer report 'WARNING: ThreadSanitizer: data race ... Write of size 8 ... #0 Curl_llist_insert_next lib/llist.c:115 #1 Curl_llist_append #2 cf_scache_peer_add_session lib/vtls/vtls_scache.c:751 #3 Curl_ssl_scache_put lib/vtls/vtls_scache.c:781 #4 Curl_ossl_add_session ... #6 ossl_new_session_cb ... SUMMARY: ThreadSanitizer: data race ... Curl_llist_insert_next'. An earlier identical docker_shell run against the same TSan-built post_intro binary additionally captured the paired 'Previous read of size 8 ... #0 Curl_llist_count lib/llist.c:242:16 #1 Curl_ssl_scache_take lib/vtls/vtls_scache.c:828:5'. run_poc(pre_intro) and run_poc(post_benign): exit=0, crashed=False, output 'done ok=1920 fail=0', no sanitizer report, using the same /poc/run.sh reproducer.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=b399a98d2da1  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=b2cb5968487e10ae2f3893eaf97600fbac9fd533576b5ddc0ddb9099643f7b7a
  source_integrity=True
  output_tail:
    + '[' 0 -ne 0 ']'
    + CERT=/tmp/tsanbuild/src/tests/certs/Server-localhost-sv.pem
    + KEY=/tmp/tsanbuild/src/tests/certs/Server-localhost-sv.key
    + PORT=8444
    + clang -g -O0 -o /tmp/server /poc/server.c -lssl -lcrypto
    + SRV_PID=9108
    + sleep 1
    + /tmp/server 8444 /tmp/tsanbuild/src/tests/certs/Server-localhost-sv.pem /tmp/tsanbuild/src/tests/certs/Server-localhost-sv.key
    listening on 8444
    + clang -g -O1 -fsanitize=thread -fno-omit-frame-pointer -I/tmp/tsanbuild/src/include -o /tmp/poc /poc/poc.c /tmp/tsanbuild/src/lib/.libs/libcurl.a -lpthread -lssl -lcrypto -lz
    + BUILD_RC=0
    + cat /tmp/poc_build.log
    + '[' 0 -ne 0 ']'
    + TSAN_OPTIONS=halt_on_error=1:exitcode=66
    + /tmp/poc https://127.0.0.1:8444/
    + RC=0
    + kill 9108
    + wait 9108
    + echo POC_EXIT=0
    + exit 0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=66  poc_ran=True  patched=False
  commit=68bd759c2bfe  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=b2cb5968487e10ae2f3893eaf97600fbac9fd533576b5ddc0ddb9099643f7b7a
  source_integrity=True
  sanitizer:
    ==================
    WARNING: ThreadSanitizer: data race (pid=9114)
      Write of size 8 at 0x7b6800000038 by thread T10 (mutexes: write M0):
        #0 Curl_llist_insert_next /tmp/tsanbuild/src/lib/llist.c:115:3 (poc+0xdb813) (BuildId: 3d826b99001fd629ef70bf394f37366c573c201f)
        #1 Curl_llist_append /tmp/tsanbuild/src/lib/llist.c:134:3 (poc+0xdb813)
        #2 cf_scache_peer_add_session /tmp/tsanbuild/src/lib/vtls/vtls_scache.c:751:5 (poc+0x119a86) (BuildId: 3d826b99001fd629ef70bf394f37366c573c201f)
        #3 Curl_ssl_scache_put /tmp/tsanbuild/src/lib/vtls/vtls_scache.c:781:12 (poc+0x119a86)
        #4 Curl_ossl_add_session /tmp/tsanbuild/src/lib/vtls/openssl.c:2910:16 (poc+0x17b973) (BuildId: 3d826b99001fd629ef70bf394f37366c573c201f)
        #5 ossl_new_session_cb /tmp/tsanbuild/src/lib/vtls/openssl.c:2929:5 (poc+0x183e39) (BuildId: 3d826b99001fd629ef70bf394f37366c573c201f)
        #6 <null> <null> (libssl.so.3+0x3ad66) (BuildId: 7f9ef5128bd0182c9d52ccec1bf8087a47b87149)
        #7 ssl_cf_recv /tmp/tsanbuild/src/lib/vtls/vtls.c:1446:11 (poc+0x116002) (BuildId: 3d826b99001fd629ef70bf394f37366c573c201f)
        #8 Curl_cf_def_recv /tmp/tsanbuild/src/lib/cfilters.c:116:5 (poc+0x1262d3) (BuildId: 3d826b99001fd629ef70bf394f37366c573c201f)
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=b399a98d2da1  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=b2cb5968487e10ae2f3893eaf97600fbac9fd533576b5ddc0ddb9099643f7b7a
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    + '[' 0 -ne 0 ']'
    + CERT=/tmp/tsanbuild/src/tests/certs/Server-localhost-sv.pem
    + KEY=/tmp/tsanbuild/src/tests/certs/Server-localhost-sv.key
    + PORT=8444
    + clang -g -O0 -o /tmp/server /poc/server.c -lssl -lcrypto
    + SRV_PID=9108
    + sleep 1
    + /tmp/server 8444 /tmp/tsanbuild/src/tests/certs/Server-localhost-sv.pem /tmp/tsanbuild/src/tests/certs/Server-localhost-sv.key
    listening on 8444
    + clang -g -O1 -fsanitize=thread -fno-omit-frame-pointer -I/tmp/tsanbuild/src/include -o /tmp/poc /poc/poc.c /tmp/tsanbuild/src/lib/.libs/libcurl.a -lpthread -lssl -lcrypto -lz
    + BUILD_RC=0
    + cat /tmp/poc_build.log
    + '[' 0 -ne 0 ']'
    + TSAN_OPTIONS=halt_on_error=1:exitcode=66
    + /tmp/poc https://127.0.0.1:8444/
    + RC=0
    + kill 9108
    + wait 9108
    + echo POC_EXIT=0
    + exit 0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
