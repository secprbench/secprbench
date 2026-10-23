# Verification report: pr_review_GH-17274

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: NullPointerDereference
- **Intro commit**: `ebd9d67b8a4fb50673b8a255ee3b14180d7313c2`
- **Intro parent**: `9b0c0d6ade052c46cf72d2fd43017bacb0ba07f6`
- **Fix commit**: `3a2689712afb0c8e2b489bf17d17cbd392c6aa7b`
- **Affected files**: ['lib/vtls/vtls.c']

## PoC
- source: agent-generated (initial source: no_poc)
- dir: `/research-data/secprbench/season100-balanced-20261001/verification/cases/curl/17e5a8f7fff8d6517b1e/attempts/01/pocs/curl/GH-17274`
- input: `pin.pem` (53 bytes)
- run.sh: False

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- Confirmed root cause exactly as described in meta.json: pubkey_pem_to_der() in lib/vtls/vtls.c strips newlines from the PEM body into a lazily-allocated dynbuf (pbuf) and, in the introduced revision, unconditionally passes Curl_dyn_ptr(&pbuf) to Curl_base64_decode() even when zero bytes were ever appended (PEM body consisting solely of blank/newline characters) — in which case Curl_dyn_ptr() legitimately returns NULL and Curl_base64_decode()'s internal strlen(src) dereferences that NULL pointer. No existing PoC/run.sh was present, so I wrote a minimal C harness (/poc/poc.c) linking directly against the already-built lib/.libs/libcurl.a (Curl_pin_peer_pubkey confirmed to be an exported, non-hidden symbol via nm) and calling Curl_pin_peer_pubkey() directly with a crafted pinned-public-key PEM file (/poc/pin.pem) whose body is blank, exactly reaching Curl_pin_peer_pubkey -> pubkey_pem_to_der -> Curl_base64_decode(NULL,...). I built pre_intro (9b0c0d6ade05), post_intro (ebd9d67b8a4f) and post_benign (fix 3a2689712afb, verified by inspecting the source diff showing the restored Curl_dyn_len() guard), then ran the identical compile+execute command via run_poc on all three under ASan+UBSan. Only post_intro aborts with a clear UBSan 'null pointer passed as argument declared never-null' report at the exact Curl_base64_decode call site reached through pubkey_pem_to_der/Curl_pin_peer_pubkey; pre_intro and post_benign both complete cleanly returning CURLE_BAD_CONTENT_ENCODING with no sanitizer report. This cleanly establishes introduction=yes and benign(fix)=yes for the labelled NullPointerDereference bug.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.
- bug_marker: "UBSan abort: \"base64.c:91:12: runtime error: null pointer passed as argument 1, which is declared to never be null\" with stack Curl_base64_decode -> pubkey_pem_to_der (vtls.c:988) -> Curl_pin_peer_pubkey (vtls.c:1134) -> main; run_poc reports crashed=True, exit=1."
- pre_marker: "run_poc output: \"Curl_pin_peer_pubkey returned 90\" (CURLE_BAD_CONTENT_ENCODING), crashed=False, exit=0, no sanitizer report."
- benign_marker: "run_poc output: \"Curl_pin_peer_pubkey returned 90\" (CURLE_BAD_CONTENT_ENCODING), crashed=False, exit=0, no sanitizer report; source inspection of vtls.c in this build shows the restored guard `if(Curl_dyn_len(&pbuf)) { ... Curl_base64_decode(...) }` before calling Curl_base64_decode."
- target execution: Identical input PEM file (/poc/pin.pem, BEGIN/END PUBLIC KEY markers with an all-blank body) and identical harness invocation (same compiled poc.c calling Curl_pin_peer_pubkey) executed via run_poc across all three builds: pre_intro (commit 9b0c0d6ade05), post_intro (commit ebd9d67b8a4f), post_benign (fix 3a2689712afb, confirmed by source diff). Only post_intro dereferences the NULL pointer returned by Curl_dyn_ptr() on an empty dynbuf via strlen() inside Curl_base64_decode, caught by UBSan's nonnull-attribute check (a NULL-pointer-dereference equivalent). pre_intro and post_benign both safely detect the empty/invalid PEM body and return CURLE_BAD_CONTENT_ENCODING (90) without touching the NULL pointer, with identical output and exit codes.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=9b0c0d6ade05  note=build cached
  command=bash -c 'cd /tmp && gcc -g -O1 -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer -DHAVE_CONFIG_H=1 -I/work/lib -I/work/include -I/work/lib/vtls -o poc /poc/poc.c /work/lib/.libs/libcurl.a -lssl -lcrypto -lz -lpthread && ASAN_OPTIONS=detect_leaks=0 ./poc'
  poc_sha256=e57bce423c73257842ba5bb6a5f425049abf73795d43077deb77d1afa3ca123b
  source_integrity=True
  output_tail:
    Curl_pin_peer_pubkey returned 90
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=1  poc_ran=True  patched=False
  commit=ebd9d67b8a4f  note=build cached
  command=bash -c 'cd /tmp && gcc -g -O1 -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer -DHAVE_CONFIG_H=1 -I/work/lib -I/work/include -I/work/lib/vtls -o poc /poc/poc.c /work/lib/.libs/libcurl.a -lssl -lcrypto -lz -lpthread && ASAN_OPTIONS=detect_leaks=0 ./poc'
  poc_sha256=e57bce423c73257842ba5bb6a5f425049abf73795d43077deb77d1afa3ca123b
  source_integrity=True
  sanitizer:
    VERIFY_EXIT=1
    
    base64.c:91:12: runtime error: null pointer passed as argument 1, which is declared to never be null
        #0 0x5612d2c4649d in Curl_base64_decode /work/lib/base64.c:91
        #1 0x5612d2c38614 in pubkey_pem_to_der vtls/vtls.c:988
        #2 0x5612d2c38614 in Curl_pin_peer_pubkey vtls/vtls.c:1134
        #3 0x5612d2b9c06d in main /poc/poc.c:23
        #4 0x7fba77bffd8f in __libc_start_call_main ../sysdeps/nptl/libc_start_call_main.h:58
        #5 0x7fba77bffe3f in __libc_start_main_impl ../csu/libc-start.c:392
        #6 0x5612d2b9bee4 in _start (/tmp/poc+0x219ee4)
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=9b0c0d6ade05  note=build cached
  command=bash -c 'cd /tmp && gcc -g -O1 -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer -DHAVE_CONFIG_H=1 -I/work/lib -I/work/include -I/work/lib/vtls -o poc /poc/poc.c /work/lib/.libs/libcurl.a -lssl -lcrypto -lz -lpthread && ASAN_OPTIONS=detect_leaks=0 ./poc'
  poc_sha256=e57bce423c73257842ba5bb6a5f425049abf73795d43077deb77d1afa3ca123b
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    Curl_pin_peer_pubkey returned 90
    VERIFY_EXIT=0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
