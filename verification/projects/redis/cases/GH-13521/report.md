# Verification report: pr_review_GH-13521

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: NullPointerDereference
- **Intro commit**: `701f06657d20ec42f0cf78de0ac9d7197e44c00c`
- **Intro parent**: `cf838038802b6d5049e3368953a3a737dd3aaee5`
- **Fix commit**: `08d714d0e5d59f1c1ca37cff1724849220fb6daf`
- **Affected files**: ['src/server.c', 'src/networking.c']

## PoC
- source: agent-generated (initial source: candidate_only)
- dir: `/research-data/secprbench/season100-balanced-20261001/verification/cases/redis/f7a07153a2141a66711c/attempts/01/pocs/redis/GH-13521`
- input: `None` (0 bytes)
- run.sh: True

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- meta.json/discussion.md describe GH-13521 introducing a cron-based client->argv release: clientsCronFreeArgvIfIdle() frees argv and zeroes argv_len whenever c->argc==0 and the client has been idle 2s, without checking c->multibulklen, so a client that sent only a multibulk header (args still pending) is wrongly treated as idle. The upstream fix (08d714d0e5d5) adds the multibulklen check (confirmed present in post_benign's clientsCronFreeArgvIfIdle: "if (!c->argv || c->multibulklen || c->argc) return 0;") and also fixes argv_len bookkeeping. I built pre_intro (cf838038, which predates the cron-argv-free feature entirely -- it has no clientsCronFreeArgvIfIdle function at all), post_intro (701f0665, the buggy version), and post_benign (base + the fix patch applied, confirmed by grepping server.c) with sanitizers in Docker. I wrote a run.sh that launches redis-server in the background, waits for readiness, runs the python poc client that performs the exact socket sequence above, then (crucially) uses `wait $SRV_PID` to propagate the server's own exit/signal status as run.sh's exit code so crash detection is unambiguous. Running the identical reproducer via run_poc against all three builds: post_intro -> exit=1, crashed=True, UndefinedBehaviorSanitizer reported "applying non-zero offset 8 to null pointer" in processMultibulkBuffer (networking.c:2516), immediately followed by an ASan abort ("nested bug in the same thread"), stack trace processMultibulkBuffer -> processInputBuffer -> readQueryFromClient -> connSocketEventHandler -> aeProcessEvents -> aeMain -> main -- exactly the argv-after-cron-free code path named in the bug/fix commit. pre_intro -> exit=0, crashed=False, server alive, SET returned "+OK\r\n" as expected. post_benign -> exit=0, crashed=False, server alive, SET returned "+OK\r\n" as expected. The same command/input was used across all three builds, satisfying the invariance requirement. This conclusively confirms introduction by the intro commit and resolution by the benign/fix commit.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=cf838038802b  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=11d28fec10cf111e312f3b9c09908de7f85f53dcc219c354947aeed0cbec6cea
  source_integrity=True
  output_tail:
    POC_RESULT: got response: b'+OK\r\n'
    POC_RESULT: OK_AS_EXPECTED
    SERVER_STILL_ALIVE (poc rc=0)
    ---- redis log ----
    10:C 01 Oct 2026 21:32:24.523 # WARNING Memory overcommit must be enabled! Without it, a background save or replication may fail under low memory condition. To fix this issue add 'vm.overcommit_memory = 1' to /etc/sysctl.conf and then reboot or run the command 'sysctl vm.overcommit_memory=1' for this to take effect.
    10:C 01 Oct 2026 21:32:24.523 * oO0OoO0OoO0Oo Redis is starting oO0OoO0OoO0Oo
    10:C 01 Oct 2026 21:32:24.523 * Redis version=255.255.255, bits=64, commit=00000000, modified=0, pid=10, just started
    10:C 01 Oct 2026 21:32:24.523 * Configuration loaded
    10:M 01 Oct 2026 21:32:24.526 * monotonic clock: POSIX clock_gettime
    10:M 01 Oct 2026 21:32:24.528 * Running mode=standalone, port=7799.
    10:M 01 Oct 2026 21:32:24.529 * Server initialized
    10:M 01 Oct 2026 21:32:24.529 * Ready to accept connections tcp
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=1  poc_ran=True  patched=False
  commit=701f06657d20  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=11d28fec10cf111e312f3b9c09908de7f85f53dcc219c354947aeed0cbec6cea
  source_integrity=True
  sanitizer:
     (12288 bytes)
    *** Preparing to test memory region 7f5ace87a000 (24576 bytes)
    *** Preparing to test memory region 7f5ace8b7000 (4096 bytes)
    .server exit status: 1
    VERIFY_EXIT=1
    
    networking.c:2516:17: runtime error: applying non-zero offset 8 to null pointer
        #0 0x55797efa3322 in processMultibulkBuffer /work/src/networking.c:2516:36
        #1 0x55797efa4087 in processInputBuffer /work/src/networking.c:2673:17
        #2 0x55797ef8fdbc in readQueryFromClient /work/src/networking.c:2863:9
        #3 0x55797f211c19 in callHandler /work/src/./connhelpers.h:58:18
        #4 0x55797f20fb12 in connSocketEventHandler /work/src/socket.c:277:14
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=cf838038802b  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=11d28fec10cf111e312f3b9c09908de7f85f53dcc219c354947aeed0cbec6cea
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    POC_RESULT: got response: b'+OK\r\n'
    POC_RESULT: OK_AS_EXPECTED
    SERVER_STILL_ALIVE (poc rc=0)
    ---- redis log ----
    10:C 01 Oct 2026 21:32:33.273 # WARNING Memory overcommit must be enabled! Without it, a background save or replication may fail under low memory condition. To fix this issue add 'vm.overcommit_memory = 1' to /etc/sysctl.conf and then reboot or run the command 'sysctl vm.overcommit_memory=1' for this to take effect.
    10:C 01 Oct 2026 21:32:33.273 * oO0OoO0OoO0Oo Redis is starting oO0OoO0OoO0Oo
    10:C 01 Oct 2026 21:32:33.273 * Redis version=255.255.255, bits=64, commit=00000000, modified=0, pid=10, just started
    10:C 01 Oct 2026 21:32:33.273 * Configuration loaded
    10:M 01 Oct 2026 21:32:33.277 * monotonic clock: POSIX clock_gettime
    10:M 01 Oct 2026 21:32:33.280 * Running mode=standalone, port=7799.
    10:M 01 Oct 2026 21:32:33.281 * Server initialized
    10:M 01 Oct 2026 21:32:33.282 * Ready to accept connections tcp
    VERIFY_EXIT=0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
