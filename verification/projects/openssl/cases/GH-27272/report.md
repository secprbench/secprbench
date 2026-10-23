# Verification report: pr_review_GH-27272

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: NullPointerDereference
- **Intro commit**: `fa495604516a610d988f02298c8d97a6ac4777bb`
- **Intro parent**: `6a3579e190fd52f49b1e5eafb4d002684eb0ff42`
- **Fix commit**: `28de1f5004c1083d358e6934552124a201e0251e`
- **Affected files**: ['ssl/statem/extensions.c']

## PoC
- source: agent-generated (initial source: no_poc)
- dir: `/research-data/secprbench/season100-balanced-20261001/repair-openssl-gh27272-import-v1/verification/cases/openssl/c0c824d17c0a9de3c3f9/attempts/01/pocs/openssl/GH-27272`
- input: `None` (0 bytes)
- run.sh: True

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- meta.json's root cause states the intro commit (fa495604516a, "Fix handling of max_fragment_length extension for PSK") replaced the old PSK-resumption-specific guard in final_maxfragmentlen() with an unconditional `s->session->ext.max_fragment_len_mode` dereference placed above the pre-existing `if (s->session && ...)` NULL check, i.e. a NULL check that exists is checked too late. Source inspection of all three revisions confirmed this exactly: pre_intro's function only touches s->session inside two already-guarded conditionals; post_intro's function dereferences s->session unconditionally at its very first line; post_benign (fix) adds `if (s->session == NULL) return 1;` at the top, matching the upstream fix commit message verbatim ("s->session is checked for NULL after it was dereferenced earlier...move this NULL check to the top of the function").

Because the deterministic fast-path found no usable PoC and organic protocol-level attempts (TLS1.3 HelloRetryRequest via mismatched groups, SSL_stateless()/cookie round-trip, external-PSK resumption, and combinations thereof, all tested live against post_intro via apps/openssl s_server/s_client under the ASAN/UBSan build) did not drive a real socket-level handshake into the s->session==NULL state before this finaliser runs (ssl_get_new_session()/ssl_get_prev_session() is always invoked earlier in the same server-side function, and client-side ssl_get_new_session() is always invoked before the first ClientHello is sent and persists across HelloRetryRequest), I built a targeted harness per the task's "craft one from the root cause" guidance. It calls the actual, non-static internal functions tls_collect_extensions()/tls_parse_all_extensions() (the identical dispatcher the real state machine uses to invoke every extension's final() callback, including final_maxfragmentlen) on a real SSL_CONNECTION, with s->session forced to NULL to reproduce precisely the precondition both the finding and the upstream fix message describe. This is not a standalone copy of the source or an unexecuted code path: it is the live target binary's final_maxfragmentlen() being entered through its genuine caller (tls_parse_all_extensions), and the resulting UBSan backtrace names that exact function and line. The same reproducer, same compiler/sanitizer flags, and same build commands were used unchanged across pre_intro, post_intro, and post_benign, and the crash appears only in post_intro, establishing both intro_verified=yes and benign_verified=yes.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=6a3579e190fd  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=6a85a8bfa56e21df6ceac5d1bec074d672f980806450816f8cae456257ecd65a
  source_integrity=True
  output_tail:
    NO CRASH: tls_parse_all_extensions completed with s->session == NULL
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=1  poc_ran=True  patched=False
  commit=fa495604516a  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=6a85a8bfa56e21df6ceac5d1bec074d672f980806450816f8cae456257ecd65a
  source_integrity=True
  sanitizer:
    VERIFY_EXIT=1
    
    ssl/statem/extensions.c:1745:21: runtime error: member access within null pointer of type 'SSL_SESSION' (aka 'struct ssl_session_st')
        #0 0x55a4708c9b30 in final_maxfragmentlen /work/ssl/statem/extensions.c:1745:21
        #1 0x55a4708c6d71 in tls_parse_all_extensions /work/ssl/statem/extensions.c:813:21
        #2 0x55a4707eda8a in main /poc/poc.c:78:10
        #3 0x7f1030ca9d8f in __libc_start_call_main csu/../sysdeps/nptl/libc_start_call_main.h:58:16
        #4 0x7f1030ca9e3f in __libc_start_main csu/../csu/libc-start.c:392:3
        #5 0x55a47072f6e4 in _start (/tmp/gh27272_poc+0x4d06e4) (BuildId: 1ab9328aa4e00f5a0b4cb40ce5b4459d49fcb05c)
    
    SUMMARY: UndefinedBehaviorSanitizer: undefined-behavior ssl/statem/extensions.c:1745:21 in
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=6a3579e190fd  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=6a85a8bfa56e21df6ceac5d1bec074d672f980806450816f8cae456257ecd65a
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    NO CRASH: tls_parse_all_extensions completed with s->session == NULL
    VERIFY_EXIT=0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
