# Verification report: pr_review_GH-13495

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: UseAfterFree
- **Intro commit**: `a7afd1d2b2b0b9b64c44fd950d57e49ad8823bde`
- **Intro parent**: `3fcddfb61f903d7112da186cba8b1c93a99dc87f`
- **Fix commit**: `a0da8390a28a92e7068fef7a00ebc9b767e70500`
- **Affected files**: ['src/replication.c']

## PoC
- source: agent-generated (initial source: candidate_only)
- dir: `/research-data/secprbench/season100-balanced-20261001/verification/cases/redis/ac5b49ed8ac064a862f9/attempts/01/pocs/redis/GH-13495`
- input: `None` (0 bytes)
- run.sh: True

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- meta.json's root cause: PR #13495 reordered code so emptyData() runs after functions_lib_ctx is fetched via functionsLibCtxGetCurrent(); emptyData() frees/recreates the functions lib context, leaving the captured pointer dangling. Fix commit a0da8390a28a reorders to call emptyData() before fetching the pointer. No existing PoC/run.sh was provided (fast-path found none), so I inspected src/replication.c in post_intro directly: lines ~2061-2103 show the non-SWAPDB branch fetching functions_lib_ctx before the later emptyData() call at line 2090, with the pointer then passed into rdbLoadingCtx used by rdbLoadRioWithLoadingCtx at line 2103; src/db.c confirmed emptyData() synchronously frees the current functions lib ctx via functionsLibCtxClearCurrent(async=0)->functionsLibCtxFree when replica-lazy-flush is no (default). I crafted run.sh exercising exactly this path: a master with a loaded Lua function library syncing diskless to an on-empty-db replica. First iteration of the script backgrounded both servers and always exited 0 regardless of a child crash, which run_poc's crash-detection read as crashed=False despite an embedded ASan report in the output (record_verdict correctly rejected that evidence). I fixed the script to detect the replica dying and `wait` on its PID to propagate the real (SIGABRT-driven) exit status, re-ran all three versions with this corrected script, and confirmed: post_intro now reports exit=1 crashed=True with a clean, unambiguous AddressSanitizer heap-use-after-free (READ in functionsCreateWithLibraryCtx <- rdbFunctionLoad <- rdbLoadRioWithLoadingCtx <- readSyncBulkPayload:2103; freed by functionsLibCtxFree <- functionsLibCtxClearCurrent <- emptyData <- readSyncBulkPayload:2090); pre_intro and post_benign both ran the identical script/config/commands and completed with exit=0 crashed=False, replica reaching full sync ('REPLICA SURVIVED / SYNCED OK'), no sanitizer report. This satisfies the same-reproducer invariance requirement and cleanly distinguishes introduction (post_intro only) from parent and companion fix.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=3fcddfb61f90  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=e06e695b6d88b36e9cb2b579c425c4a6b4a05c651d33fa1714285b887ad6cef0
  source_integrity=True
  output_tail:
     * Configuration loaded
    10:M 02 Oct 2026 00:24:44.827 * monotonic clock: POSIX clock_gettime
    10:M 02 Oct 2026 00:24:44.829 * Running mode=standalone, port=7700.
    10:M 02 Oct 2026 00:24:44.830 * Server initialized
    10:M 02 Oct 2026 00:24:44.830 * Ready to accept connections tcp
    10:M 02 Oct 2026 00:24:45.856 * Replica 127.0.0.1:7701 asks for synchronization
    10:M 02 Oct 2026 00:24:45.856 * Partial resynchronization not accepted: Replication ID mismatch (Replica asked for '4382a165a2a1d4924b1abe64299ba88fdc89739f', my replication IDs are 'a3bbf65cd7e9ef48c17440d6f22ca64c0acf7db7' and '0000000000000000000000000000000000000000')
    10:M 02 Oct 2026 00:24:45.856 * Replication backlog created, my new replication IDs are '2c620061f89ff9cac20efe13d67504223f2d4247' and '0000000000000000000000000000000000000000'
    10:M 02 Oct 2026 00:24:45.856 * Starting BGSAVE for SYNC with target: replicas sockets
    10:M 02 Oct 2026 00:24:45.858 * Background RDB transfer started by pid 27
    27:C 02 Oct 2026 00:24:45.863 * Fork CoW for RDB: current 0 MB, peak 0 MB, average 0 MB
    10:M 02 Oct 2026 00:24:45.863 * Diskless rdb transfer, done reading from pipe, 1 replicas still up.
    REPLICA SURVIVED / SYNCED OK
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=1  poc_ran=True  patched=False
  commit=a7afd1d2b2b0  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=e06e695b6d88b36e9cb2b579c425c4a6b4a05c651d33fa1714285b887ad6cef0
  source_integrity=True
  sanitizer:
    succeeded
    10:M 02 Oct 2026 00:24:41.360 * Connection with replica 127.0.0.1:7701 lost.
    REPLICA PROCESS DIED rc=1
    VERIFY_EXIT=1
    
    =================================================================
    ==11==ERROR: AddressSanitizer: heap-use-after-free on address 0x60300001d710 at pc 0x5652a5330c4b bp 0x7ffd5f0642b0 sp 0x7ffd5f0642a8
    READ of size 8 at 0x60300001d710 thread T0
        #0 0x5652a5330c4a in functionsCreateWithLibraryCtx /work/src/functions.c:970:38
        #1 0x5652a511a293 in rdbFunctionLoad /work/src/rdb.c:3297:30
        #2 0x5652a511b0a7 in rdbLoadRioWithLoadingCtx /work/src/rdb.c:3557:17
        #3 0x5652a50f75ec in readSyncBulkPayload /work/src/replication.c:2103:13
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=3fcddfb61f90  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=e06e695b6d88b36e9cb2b579c425c4a6b4a05c651d33fa1714285b887ad6cef0
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
     * Configuration loaded
    10:M 02 Oct 2026 00:24:47.001 * monotonic clock: POSIX clock_gettime
    10:M 02 Oct 2026 00:24:47.003 * Running mode=standalone, port=7700.
    10:M 02 Oct 2026 00:24:47.004 * Server initialized
    10:M 02 Oct 2026 00:24:47.004 * Ready to accept connections tcp
    10:M 02 Oct 2026 00:24:48.026 * Replica 127.0.0.1:7701 asks for synchronization
    10:M 02 Oct 2026 00:24:48.026 * Partial resynchronization not accepted: Replication ID mismatch (Replica asked for 'abe94edc65b75df05d7cf0cbbda43dc4a05fb96e', my replication IDs are '2910bbbb96d44902617e99308dfd804706abdb79' and '0000000000000000000000000000000000000000')
    10:M 02 Oct 2026 00:24:48.026 * Replication backlog created, my new replication IDs are 'e2a317500ee7aecd042e139057ab9880965a6ea9' and '0000000000000000000000000000000000000000'
    10:M 02 Oct 2026 00:24:48.026 * Starting BGSAVE for SYNC with target: replicas sockets
    10:M 02 Oct 2026 00:24:48.028 * Background RDB transfer started by pid 26
    26:C 02 Oct 2026 00:24:48.033 * Fork CoW for RDB: current 0 MB, peak 0 MB, average 0 MB
    10:M 02 Oct 2026 00:24:48.033 * Diskless rdb transfer, done reading from pipe, 1 replicas still up.
    REPLICA SURVIVED / SYNCED OK
    VERIFY_EXIT=0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
