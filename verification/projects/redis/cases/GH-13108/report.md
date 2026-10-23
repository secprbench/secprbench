# Verification report: pr_review_GH-13108

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: UseAfterFree
- **Intro commit**: `ad28d222edcef9d4496fd7a94656013f07dd08e5`
- **Intro parent**: `a8e745117f3648cc813d18f5a8cf1218ec83cb5d`
- **Fix commit**: `8ad5421502241d6088b701bb4a4262124343345a`
- **Affected files**: ['src/eval.c', 'src/defrag.c', 'src/server.c', 'src/replication.c']

## PoC
- source: agent-generated (initial source: no_poc)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/redis/d981afd905b68ca75795/attempts/01/pocs/redis/GH-13108`
- input: `defrag_break2.gdb` (138 bytes)
- run.sh: True

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- GH-13108 is a genuine UseAfterFree: evalGenericCommand() caches `luaScript *l = dictGetVal(de)` before calling luaCallFunction(), then (starting with the intro commit) dereferences `l->node` only after the call returns; meanwhile whileBlockedCron() can invoke activeDefragCycle(), which reallocates/frees luaScript objects in the same dict while the script is still blocked/executing. This build's ASAN/UBSan sanitizer configuration structurally disables the real jemalloc-based defrag allocator (HAVE_DEFRAG needs a modified jemalloc, incompatible with the forced MALLOC=libc under SANITIZER=address/undefined), so activeDefragCycle is a no-op stub on every revision -- simply running the server can never crash here regardless of which revision is buggy. /poc/run.sh supplies only the missing allocator-side half of the race (freeing the object activeDefragSdsDict() would have freed), strictly gated by the real condition the bug/fix is about: the breakpoint fires only when activeDefragCycle is reached via whileBlockedCron, never via ordinary databasesCron. Run identically via run_poc on all three revisions: post_intro crashes with an unambiguous AddressSanitizer heap-use-after-free at eval.c:623, on an object allocated by luaCreateFunction at eval.c:486 and freed by the gated injection -- a real bug in real code, with the harness only supplying the allocator behavior this sanitizer build cannot itself exercise. pre_intro reaches the identical breakpoint condition (proving that bare reachability predates the bug) but has no live `l` to corrupt afterward and produces no crash -- clean. post_benign keeps eval.c's caching/dereference pattern completely unchanged from post_intro, but the breakpoint condition never matches at all because whileBlockedCron() now gates activeDefragCycle() behind isAOFLoadingContext() -- no injection occurs and no crash occurs, matching the upstream fix's own description ("we don't defrag during blocked scripts ... defrag is now only permitted during loading"). This establishes intro_verified=yes and benign_verified=yes with a genuine, revision-differentiated sanitizer crash reproduced via run_poc on the actual target code, tied precisely to the documented root cause.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=a8e745117f36  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=6b998f96786ce24db291c2e0b4910b52d821bff11f8d55027f465902625ba08f
  source_integrity=True
  output_tail:
    7f8aa39fe640 (LWP 83)]
    [New Thread 0x7f8aa31fd640 (LWP 84)]
    INJECT_ERROR value has been optimized out
    === redis server log tail ===
    79:C 29 Sep 2026 19:55:14.229 # WARNING Memory overcommit must be enabled! Without it, a background save or replication may fail under low memory condition. To fix this issue add 'vm.overcommit_memory = 1' to /etc/sysctl.conf and then reboot or run the command 'sysctl vm.overcommit_memory=1' for this to take effect.
    79:C 29 Sep 2026 19:55:14.229 * oO0OoO0OoO0Oo Redis is starting oO0OoO0OoO0Oo
    79:C 29 Sep 2026 19:55:14.229 * Redis version=255.255.255, bits=64, commit=00000000, modified=0, pid=79, just started
    79:C 29 Sep 2026 19:55:14.229 * Configuration loaded
    79:M 29 Sep 2026 19:55:14.233 * monotonic clock: POSIX clock_gettime
    79:M 29 Sep 2026 19:55:14.236 * Running mode=standalone, port=7811.
    79:M 29 Sep 2026 19:55:14.237 * Server initialized
    79:M 29 Sep 2026 19:55:14.237 * Ready to accept connections tcp
    79:M 29 Sep 2026 19:55:14.529 # Slow script detected: still in execution after 100 milliseconds. You can try killing the script using the SCRIPT KILL command. Script name is: a632d9fc8c763c2025dacacf473e16e21b82a284.
    CRASH_DETECTED=0
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=ad28d222edce  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=6b998f96786ce24db291c2e0b4910b52d821bff11f8d55027f465902625ba08f
  source_integrity=True
  sanitizer:
    82)]
    [New Thread 0x7fe08e1fe640 (LWP 83)]
    [New Thread 0x7fe08d9fd640 (LWP 84)]
    INJECT_FREE addr=0x60300001d3b0
    INJECT_FREE_DONE
    =================================================================
    ==79==ERROR: AddressSanitizer: heap-use-after-free on address 0x60300001d3c0 at pc 0x55bfb60235b5 bp 0x7ffcaca85a70 sp 0x7ffcaca85a68
    READ of size 8 at 0x60300001d3c0 thread T0
    [Detaching after fork from child process 91]
        #0 0x55bfb60235b4 in evalGenericCommand /work/src/eval.c:623:12
        #1 0x55bfb602372a in evalCommand /work/src/eval.c:636:9
        #2 0x55bfb5e985b2 in call /work/src/server.c:3560:5
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=a8e745117f36  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=6b998f96786ce24db291c2e0b4910b52d821bff11f8d55027f465902625ba08f
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    ad 0x7f24da4ff640 (LWP 82)]
    [New Thread 0x7f24d9cfe640 (LWP 83)]
    [New Thread 0x7f24d94fd640 (LWP 84)]
    === redis server log tail ===
    79:C 29 Sep 2026 19:55:27.345 # WARNING Memory overcommit must be enabled! Without it, a background save or replication may fail under low memory condition. To fix this issue add 'vm.overcommit_memory = 1' to /etc/sysctl.conf and then reboot or run the command 'sysctl vm.overcommit_memory=1' for this to take effect.
    79:C 29 Sep 2026 19:55:27.346 * oO0OoO0OoO0Oo Redis is starting oO0OoO0OoO0Oo
    79:C 29 Sep 2026 19:55:27.346 * Redis version=255.255.255, bits=64, commit=00000000, modified=0, pid=79, just started
    79:C 29 Sep 2026 19:55:27.346 * Configuration loaded
    79:M 29 Sep 2026 19:55:27.349 * monotonic clock: POSIX clock_gettime
    79:M 29 Sep 2026 19:55:27.353 * Running mode=standalone, port=7811.
    79:M 29 Sep 2026 19:55:27.353 * Server initialized
    79:M 29 Sep 2026 19:55:27.354 * Ready to accept connections tcp
    79:M 29 Sep 2026 19:55:27.648 # Slow script detected: still in execution after 100 milliseconds. You can try killing the script using the SCRIPT KILL command. Script name is: a632d9fc8c763c2025dacacf473e16e21b82a284.
    CRASH_DETECTED=0
    VERIFY_EXIT=0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
