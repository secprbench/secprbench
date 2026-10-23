# Verification report: pr_review_GH-14323

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: UseAfterFree
- **Intro commit**: `5d0d64b062c160093dc287ed5d18ec7c807873cf`
- **Intro parent**: `090f6252c4e1a17528124b6c6b69f352fb68176f`
- **Fix commit**: `d649637ebd1b7b7792a4224a42e1ef8824743378`
- **Affected files**: ['src/defrag.c']

## PoC
- source: agent-generated (initial source: no_poc)
- dir: `/research-data/secprbench/season100-balanced-20261001/verification/cases/redis/a03f6efb4462f8f9687e/attempts/01/pocs/redis/GH-14323`
- input: `None` (0 bytes)
- run.sh: True

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- Root cause matches meta.json exactly: in post_intro's activeDefragHExpiresOB (src/defrag.c), `sds keystr = kvobjGetKey(kvobj)` captures a pointer into the original kvobj's embedded memory, then `kvobj = activeDefragAlloc(kvobj)` reallocates-and-frees the old kvobj (real activeDefragAlloc: zmalloc_no_tcache + memcpy + zfree_no_tcache(ptr)) whenever the allocator hint says the allocation should move, and the code afterwards does `kvstoreDictFindLink(db->keys, slot, keystr, NULL)` using the now-dangling `keystr` - a heap-use-after-free, confirmed directly by ASAN pointing at that exact line/call chain. This benchmark's ASAN build forces MALLOC=libc (src/Makefile: `ifeq ($(SANITIZER),address) MALLOC=libc`), so the real HAVE_DEFRAG path (gated by `#if defined(USE_JEMALLOC) && defined(JEMALLOC_FRAG_HINT)` in zmalloc.h) is compiled out of the shipped redis-server entirely (confirmed via nm: no activeDefragHExpiresOB symbol; activeDefragAlloc was a 4-instruction always-return-NULL stub), and "CONFIG SET activedefrag yes" is rejected by config.c's isValidActiveDefrag(). Neither the TCL test suite (no tclsh available in this container, no root to install it) nor any config/command-driven PoC could reach the bug here, so I built a minimal auxiliary harness under /poc, run via run_poc/run.sh identically on every configured version per the rules, that recompiles only a private, untracked copy of the unmodified src/defrag.c with -DHAVE_DEFRAG so the real target function bodies execute (not a reimplementation), supplies trivial stand-ins for the two jemalloc-only hooks it calls (functionally equivalent malloc/free; je_get_defrag_hint forced to 1 so the move decision is deterministic rather than depending on real jemalloc fragmentation stats, which are orthogonal to this ordering bug), and relinks with all the target's other already-built, unmodified object files plus a tiny -Wl,--wrap=aeMain shim that runs once the stock main()'s normal server/db initialization completes - directly driving the exact same ebScanDefrag/activeDefragHExpiresOB call that defragStageHExpires() uses in production. Verified via run_poc on all three configured versions: post_intro reliably crashes with a genuine ASAN heap-use-after-free pinpointing activeDefragHExpiresOB reading memory freed moments earlier by activeDefragAlloc on the very hash kvobj the harness created; the identical harness/input against post_benign (intro commit + companion fix) completes cleanly (object still moved, hits=1, but no UAF, since the fix defers the free via activeDefragAllocWithoutFree()+explicit activeDefragFree() until after keystr's only use); and pre_intro, probed and confirmed to structurally lack the entire per-item ebuckets-defrag mechanism (ebScanDefrag/ebDefragFunctions/activeDefragHExpiresOB all absent), runs its (otherwise identical) setup and exits cleanly with no crash - confirming the bug was introduced together with this feature in the intro commit. One documented, bug-unrelated adaptation: post_benign's mechanically-composed companion patch carries over one unrelated hunk from the same upstream multi-issue fix commit (a `nack->cgroup_ref_node` reference for a separate stream-consumer-group defrag issue) whose struct member isn't present in this isolated snapshot's headers; that branch is normally dead code under this ASAN build (only reachable via -DHAVE_DEFRAG, which this harness is the first thing to ever actually compile), so run.sh neutralizes just that one line in a private /tmp copy used solely to build the auxiliary harness (a no-op on pre_intro/post_intro, which don't have it) - the tracked src/defrag.c is never modified, and this neutralization is unrelated to the HFE/UAF logic under test.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=090f6252c4e1  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=f7c677011ba9e005170abdd35920c1402d7136fc0885f0f296654abdebc0feb7
  source_integrity=True
  output_tail:
    02 Oct 2026 00:19:54.967 # WARNING Memory overcommit must be enabled! Without it, a background save or replication may fail under low memory condition. To fix this issue add 'vm.overcommit_memory = 1' to /etc/sysctl.conf and then reboot or run the command 'sysctl vm.overcommit_memory=1' for this to take effect.
    27:C 02 Oct 2026 00:19:54.968 * oO0OoO0OoO0Oo Redis is starting oO0OoO0OoO0Oo
    27:C 02 Oct 2026 00:19:54.968 * Redis version=255.255.255, bits=64, commit=00000000, modified=0, pid=27, just started
    27:C 02 Oct 2026 00:19:54.968 * Configuration loaded
    27:M 02 Oct 2026 00:19:54.970 * monotonic clock: POSIX clock_gettime
    27:M 02 Oct 2026 00:19:54.973 * Running mode=standalone, port=7799.
    27:M 02 Oct 2026 00:19:54.974 * Server initialized
    27:M 02 Oct 2026 00:19:54.974 * Ready to accept connections tcp
    HARNESS: server fully initialized, running GH-14323 PoC
    HARNESS: hexpires empty=0
    HARNESS: this revision has no per-item ebuckets-defrag API (ebScanDefrag/activeDefragHExpiresOB absent) -- the HFE active-defrag feature (and its bug) does not exist yet here; skipping the defrag step and exiting cleanly.
    HARNESS: PoC completed without a sanitizer trap
    HARNESS_RUN_EXIT=0
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=1  poc_ran=True  patched=False
  commit=5d0d64b062c1  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=f7c677011ba9e005170abdd35920c1402d7136fc0885f0f296654abdebc0feb7
  source_integrity=True
  sanitizer:
    initialized, running GH-14323 PoC
    HARNESS: hexpires empty=0
    HARNESS: starting ebScanDefrag loop (should trigger UAF under ASAN)
    =================================================================
    ==27==ERROR: AddressSanitizer: heap-use-after-free on address 0x50300001e411 at pc 0x55c4b150c030 bp 0x7ffeeb5e2cf0 sp 0x7ffeeb5e2ce0
    READ of size 1 at 0x50300001e411 thread T0
        #0 0x55c4b150c02f in sdsType sds.h:69
        #1 0x55c4b150c02f in sdslen sds.h:74
        #2 0x55c4b150c8fd in dictSdsHash /work/src/server.c:408
        #3 0x55c4b14eb902 in dictHashKey /work/src/dict.c
        #4 0x55c4b14ea0c6 in dictFindLinkInternal /work/src/dict.c:773
        #5 0x55c4b14e9e45 in dictFindLink /work/src/dict.c:844
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=090f6252c4e1  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=f7c677011ba9e005170abdd35920c1402d7136fc0885f0f296654abdebc0feb7
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    === HAS_EBSCANDEFRAG=1 ===
    === HARNESS BUILD OK (HAS_EBSCANDEFRAG=1), running PoC ===
    27:C 02 Oct 2026 00:20:01.455 # WARNING Memory overcommit must be enabled! Without it, a background save or replication may fail under low memory condition. To fix this issue add 'vm.overcommit_memory = 1' to /etc/sysctl.conf and then reboot or run the command 'sysctl vm.overcommit_memory=1' for this to take effect.
    27:C 02 Oct 2026 00:20:01.455 * oO0OoO0OoO0Oo Redis is starting oO0OoO0OoO0Oo
    27:C 02 Oct 2026 00:20:01.455 * Redis version=255.255.255, bits=64, commit=00000000, modified=0, pid=27, just started
    27:C 02 Oct 2026 00:20:01.455 * Configuration loaded
    27:M 02 Oct 2026 00:20:01.457 * monotonic clock: POSIX clock_gettime
    27:M 02 Oct 2026 00:20:01.459 * Running mode=standalone, port=7799.
    27:M 02 Oct 2026 00:20:01.461 * Server initialized
    27:M 02 Oct 2026 00:20:01.461 * Ready to accept connections tcp
    HARNESS: server fully initialized, running GH-14323 PoC
    HARNESS: hexpires empty=0
    HARNESS: starting ebScanDefrag loop (should trigger UAF under ASAN)
    HARNESS: ebScanDefrag loop finished (rounds=0) hits=1 misses=0
    HARNESS: PoC completed without a sanitizer trap
    HARNESS_RUN_EXIT=0
    VERIFY_EXIT=0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
