# Verification report: pr_review_GH-14143

- **Status**: `inconclusive`
- **Intro verified**: None
- **Benign verified**: None
- **Bug type**: LogicError
- **Intro commit**: `dcf02298110fabb3c8f0c73c096adfafb64d9134`
- **Intro parent**: `58edea7385785368e0f7503fdb6f985932933c96`
- **Fix commit**: `03816c15f75962b8e4662cee22be6f7ba6d5d9dd`
- **Affected files**: ['src/rdb.c']

## PoC
- source: agent-generated (initial source: candidate_only)
- dir: `/research-data/secprbench/season100-balanced-20261001/verification-v2/cases/redis/75a9aa25cd494c66e4d6/attempts/01/pocs/redis/GH-14143`
- input: `replication_hfe.tcl` (76933 bytes)
- run.sh: True

## Findings

- The agent claim lacks a matching admissible three-version oracle.
- Static review: diffing src/rdb.c across the three revisions shows intro commit dcf02298110f adds, for RDB_TYPE_HASH_METADATA object loading, a new block that reads an 8-byte 'min expiration time' and on rioGetReadError() calls rdbReportCorruptRDB(\"Hash failed loading minExpire\") i.e. rdbReportError(corruption_error=1,...). In rdbReportError, the diskless-load branch (reached whenever not RESTORE/rdbCheckMode/file-based-load -- exactly the replica-diskless-load-from-socket case) unconditionally falls through to exit(1) for corruption_error=1, regardless of whether the failure was a genuine corrupt file or merely a dropped/short network read. The fix commit 03816c15f759 mechanically swaps only that call to rdbReportReadError(...) (corruption_error=0), whose branch logs and returns without exiting, matching the upstream fix message 'Fix short read of hfe key that causes exit() on replica'. pre_intro (parent 58edea738578) has no such minExpire-read block at all for this object type (confirmed by direct source diff at the call site).

Dynamic reproduction: built pre_intro, post_intro and post_benign, and ran the identical /poc/run.sh + /poc/fake_master.py PoC (a crafted, deliberately truncated diskless-replication RDB stream that cuts off mid-way through the HFE min-expire field, then closes the socket) against each via run_poc. post_intro: replica logs the exact 'Hash failed loading minExpire'/'Failure loading rdb format' message at rdb.c:2274, then 'Terminating server after rdb file reading failure.' and the process exits (REPLICA_ALIVE=no, PING refused) -- reproducing the reported exit() on a benign short read. post_benign: identical call site/message, but the log instead ends '...assuming connection error, resuming operation.', no exit -- the replica process stays alive and answers PING -- confirming the fix. pre_intro: the vulnerable code path does not exist at all (no MINEXPIRE_LOG_LINE produced, by source inspection it's structurally unreachable), and the same PoC bytes do not crash the process either (REPLICA_ALIVE=yes/PONG), consistent with introduction=yes/benign=yes.

## Agent oracle

- machine gate: inconclusive (unproven)
- basis: The agent claim lacks a matching admissible three-version oracle.
- bug_marker: "MINEXPIRE_LOG_LINE: Internal error in RDB reading offset 0, function at rdb.c:2274 -> Hash failed loading minExpire. Failure loading rdb format\nTERMINATE_LOG_LINE: Terminating server after rdb file reading failure.\nREPLICA_ALIVE=no"
- pre_marker: "MINEXPIRE_LOG_LINE: \nTERMINATE_LOG_LINE: \nREPLICA_ALIVE=yes\nPING_RESULT=PONG"
- benign_marker: "MINEXPIRE_LOG_LINE: Internal error in RDB reading offset 0, function at rdb.c:2274 -> Hash failed loading minExpire. Failure loading rdb format from socket, assuming connection error, resuming operation.\nTERMINATE_LOG_LINE: \nREPLICA_ALIVE=yes\nPING_RESULT=PONG"
- target execution: run_poc(post_intro): REPLICA_ALIVE=no; PING_RESULT=Could not connect to Redis at 127.0.0.1:10102: Connection refused; MINEXPIRE_LOG_LINE: Internal error in RDB reading offset 0, function at rdb.c:2274 -> Hash failed loading minExpire. Failure loading rdb format; TERMINATE_LOG_LINE: Terminating server after rdb file reading failure.
run_poc(post_benign): REPLICA_ALIVE=yes; PING_RESULT=PONG; MINEXPIRE_LOG_LINE: Internal error in RDB reading offset 0, function at rdb.c:2274 -> Hash failed loading minExpire. Failure loading rdb format from socket, assuming connection error, resuming operation.; TERMINATE_LOG_LINE: (empty)
run_poc(pre_intro): REPLICA_ALIVE=yes; PING_RESULT=PONG; MINEXPIRE_LOG_LINE: (empty, this code path does not exist in src/rdb.c at commit 58edea738578 -- confirmed by source diff: the whole 'load next/min expiration time' block for RDB_TYPE_HASH_METADATA, present at post_intro/post_benign rdb.c:2261-2275, is absent in pre_intro); TERMINATE_LOG_LINE: (empty)

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=58edea738578  note=build cached
  command=bash /poc/run.sh /work
  poc_sha256=6357b4f20524ba8ac47a7213fcd00cb9bb52964843496c4acea6de6f5bd49ac8
  source_integrity=True
  output_tail:
    === SUMMARY ===
    REPLICA_ALIVE=yes
    PING_RESULT=PONG
    MINEXPIRE_LOG_LINE: 
    TERMINATE_LOG_LINE: 
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=dcf02298110f  note=build cached
  command=bash /poc/run.sh /work
  poc_sha256=6357b4f20524ba8ac47a7213fcd00cb9bb52964843496c4acea6de6f5bd49ac8
  source_integrity=True
  output_tail:
    === SUMMARY ===
    REPLICA_ALIVE=no
    PING_RESULT=Could not connect to Redis at 127.0.0.1:10102: Connection refused
    MINEXPIRE_LOG_LINE: Internal error in RDB reading offset 0, function at rdb.c:2274 -> Hash failed loading minExpire. Failure loading rdb format
    TERMINATE_LOG_LINE: Terminating server after rdb file reading failure.
    VERIFY_EXIT=0
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=58edea738578  note=build cached
  command=bash /poc/run.sh /work
  poc_sha256=6357b4f20524ba8ac47a7213fcd00cb9bb52964843496c4acea6de6f5bd49ac8
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    === SUMMARY ===
    REPLICA_ALIVE=yes
    PING_RESULT=PONG
    MINEXPIRE_LOG_LINE: Internal error in RDB reading offset 0, function at rdb.c:2274 -> Hash failed loading minExpire. Failure loading rdb format from socket, assuming connection error, resuming operation.
    TERMINATE_LOG_LINE: 
    VERIFY_EXIT=0
```

## Interpretation

The available evidence does not establish both labels. Inspect the findings and per-version results for the limiting reason.
