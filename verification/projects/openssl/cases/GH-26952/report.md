# Verification report: pr_review_GH-26952

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: UseAfterFree
- **Intro commit**: `5949918f9afa85d72535676f114346ed541e0b1e`
- **Intro parent**: `65787e2dc219685c30539c6f60eb6b64b890bf6f`
- **Fix commit**: `6e7be995fd7fd24d38b95982cf90f801ac045743`
- **Affected files**: ['crypto/threads_pthread.c', 'crypto/threads_win.c']

## PoC
- source: agent-generated (initial source: candidate_only)
- dir: `/research-data/secprbench/season100-balanced-20261001/repair-openssl-gh26952-import-v1/verification/cases/openssl/a508a98e3301641fb8ed/attempts/01/pocs/openssl/GH-26952`
- input: `None` (0 bytes)
- run.sh: True

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- meta.json's root_cause: the write-side "retire in order" signal in ossl_synchronize_rcu() was placed before, rather than after, the busy-wait loop confirming the current qp has zero active readers, decoupling the order-enforcement signal from the safety condition it is meant to guarantee. I confirmed this diff directly between post_intro (buggy order) and post_benign (fixed: busy-wait moved inside the still-held prior_lock, so a later writer cannot even begin its own retire-order check until the earlier writer has verified safety). I first tried the project's own test/threadstest.c torture_rcu_high2 (the only in-repo test exercising >3 QPs, itself added by the fix PR) scaled up heavily (TSAN, 8 QPs, 32 readers, 550k+ cycles) without any report, then built a deterministic instrumented harness that proved the underlying invariant violation (two writer generations assigned/retiring one physical qp) occurs only in post_intro -- but per guidance that alone isn't sufficient for a memory-safety verdict, so I escalated to a harness (/poc/poc_orch3.c) with many concurrent ordinary RCU readers (each holding a derefed pointer across a short, realistic sleep) racing against many fast writers on the same small (4-slot) qp pool. This reliably produces a genuine AddressSanitizer heap-use-after-free in post_intro (2/2 runs via run_poc) where a filler writer's premature ossl_synchronize_rcu() return lets it free data a concurrent reader is still using, and reliably does NOT reproduce in pre_intro or post_benign (2/2 clean runs each) using the exact same reproducer invoked identically via run_poc on all three versions.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=65787e2dc219  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=63f185bf5c7b9cda0626fdc30119449e2eeebf0e73757399f052045138194e55
  source_integrity=True
  output_tail:
    DONE: no crash observed (global_seq=13022)
    RESULT: NO_CRASH (reproducer completed without AddressSanitizer report)
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=1  poc_ran=True  patched=False
  commit=5949918f9afa  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=63f185bf5c7b9cda0626fdc30119449e2eeebf0e73757399f052045138194e55
  source_integrity=True
  sanitizer:
    VERIFY_EXIT=1
    
    =================================================================
    ==15==ERROR: AddressSanitizer: heap-use-after-free on address 0x50700008a340 at pc 0x56439a24f27c bp 0x7f672e2edca0 sp 0x7f672e2edc90
    READ of size 8 at 0x50700008a340 thread T19
        #0 0x56439a24f27b in victim_thread_fn /poc/poc_orch3.c:103
        #1 0x7f673a433a82 in start_thread nptl/pthread_create.c:442
        #2 0x7f673a4c4a43 in __clone (/lib/x86_64-linux-gnu/libc.so.6+0x125a43)
    
    0x50700008a340 is located 0 bytes inside of 80-byte region [0x50700008a340,0x50700008a390)
    freed by thread T5 here:
        #0 0x7f673acb1537 in __interceptor_free ../../../../src/libsanitizer/asan/asan_malloc_linux.cpp:127
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=65787e2dc219  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=63f185bf5c7b9cda0626fdc30119449e2eeebf0e73757399f052045138194e55
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    DONE: no crash observed (global_seq=12840)
    RESULT: NO_CRASH (reproducer completed without AddressSanitizer report)
    VERIFY_EXIT=0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
