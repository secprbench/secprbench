# Verification report: pr_review_GH-13875

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: UseAfterFree
- **Intro commit**: `05aed4cab97659f748db309ae5edf79e91366634`
- **Intro parent**: `de7f2f87f74c95857ae91ee77be5a6cda18d2dea`
- **Fix commit**: `2a189709e098139b3158575ee6cb6d7ff266ed45`
- **Affected files**: ['src/t_string.c', 'tests/unit/moduleapi/keyspace_events.tcl']

## PoC
- source: agent-generated (initial source: candidate_only)
- dir: `/research-data/secprbench/season100-balanced-20261001/verification-v2/cases/redis/decec4b86c15cef34f33/attempts/01/pocs/redis/GH-13875`
- input: `keyspace_events.tcl` (3850 bytes)
- run.sh: True

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- The module's KeySpace_NotificationModuleString handler (subscribed to REDISMODULE_NOTIFY_STRING) runs synchronously from notifyKeyspaceEvent() fired during INCR, and calls RedisModule_StringDMA on the key, which invokes dbUnshareStringValue()->dbSetValue(), freeing the 'new' robj that incrDecrCommand just stored as the key's value. In post_intro (05aed4cab976, PR #13505's optimization), incrDecrCommand replies via addReplyLongLongFromStr(c,new) AFTER signalModifiedKey()/notifyKeyspaceEvent() run, so it reads 'new's string buffer after it has been freed by this reentrant module callback. run_poc on post_intro reproduced exactly the upstream-reported AddressSanitizer heap-use-after-free: addReply (networking.c:431) <- addReplyLongLongFromStr <- incrDecrCommand (t_string.c:607) <- incrCommand, freed by zfree<-decrRefCount<-dbSetValue<-dbUnshareStringValueWithDictEntry<-RM_StringDMA<-KeySpace_NotificationModuleString (tests/modules/keyspace_events.c:122) -- matching the frames in the GH-13875 report almost line-for-line. Using a large (non-shared-range) integer with maxmemory-policy allkeys-lru forces a real heap allocation (avoids the shared-integer pool that masked the bug previously, as the reporter noted) so the free is observable. The identical run.sh executed via run_poc against pre_intro (de7f2f87f74c, before the optimization) and post_benign (fix applied) both completed cleanly: INCR returned the correct value 1000000000, PING returned PONG, no sanitizer report, server stayed alive -- only post_intro crashed.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=de7f2f87f74c  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=88dc30df54231e38f20ead92b1e7f9e32d83a547defee83a15b3a7f1718aebac
  source_integrity=True
  output_tail:
    OK
    OK
    OK
    OK
    1000000000
    ---PING---
    PONG
    ---LOG TAIL---
    14:C 01 Oct 2026 23:42:49.126 # WARNING Memory overcommit must be enabled! Without it, a background save or replication may fail under low memory condition. To fix this issue add 'vm.overcommit_memory = 1' to /etc/sysctl.conf and then reboot or run the command 'sysctl vm.overcommit_memory=1' for this to take effect.
    14:C 01 Oct 2026 23:42:49.126 * oO0OoO0OoO0Oo Redis is starting oO0OoO0OoO0Oo
    14:C 01 Oct 2026 23:42:49.126 * Redis version=255.255.255, bits=64, commit=00000000, modified=0, pid=14, just started
    14:C 01 Oct 2026 23:42:49.126 * Configuration loaded
    14:M 01 Oct 2026 23:42:49.128 * monotonic clock: POSIX clock_gettime
    14:M 01 Oct 2026 23:42:49.130 * Running mode=standalone, port=7799.
    14:M 01 Oct 2026 23:42:49.131 * Module 'testkeyspace' loaded from /work/tests/modules/keyspace_events.so
    14:M 01 Oct 2026 23:42:49.131 * Server initialized
    14:M 01 Oct 2026 23:42:49.131 * Ready to accept connections tcp
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=1  poc_ran=True  patched=False
  commit=05aed4cab976  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=88dc30df54231e38f20ead92b1e7f9e32d83a547defee83a15b3a7f1718aebac
  source_integrity=True
  sanitizer:
    OK
    OK
    OK
    OK
    VERIFY_EXIT=1
    
    =================================================================
    ==14==ERROR: AddressSanitizer: heap-use-after-free on address 0x60200006b7f0 at pc 0x56512bc3888c bp 0x7fffdcf9c490 sp 0x7fffdcf9c488
    READ of size 4 at 0x60200006b7f0 thread T0
        #0 0x56512bc3888b in addReply /work/src/networking.c:431:9
        #1 0x56512bc3c894 in addReplyLongLongFromStr /work/src/networking.c:975:5
        #2 0x56512bcbd390 in incrDecrCommand /work/src/t_string.c:607:5
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=de7f2f87f74c  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=88dc30df54231e38f20ead92b1e7f9e32d83a547defee83a15b3a7f1718aebac
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    OK
    OK
    OK
    OK
    1000000000
    ---PING---
    PONG
    ---LOG TAIL---
    14:C 01 Oct 2026 23:42:51.175 # WARNING Memory overcommit must be enabled! Without it, a background save or replication may fail under low memory condition. To fix this issue add 'vm.overcommit_memory = 1' to /etc/sysctl.conf and then reboot or run the command 'sysctl vm.overcommit_memory=1' for this to take effect.
    14:C 01 Oct 2026 23:42:51.175 * oO0OoO0OoO0Oo Redis is starting oO0OoO0OoO0Oo
    14:C 01 Oct 2026 23:42:51.175 * Redis version=255.255.255, bits=64, commit=00000000, modified=0, pid=14, just started
    14:C 01 Oct 2026 23:42:51.175 * Configuration loaded
    14:M 01 Oct 2026 23:42:51.177 * monotonic clock: POSIX clock_gettime
    14:M 01 Oct 2026 23:42:51.179 * Running mode=standalone, port=7799.
    14:M 01 Oct 2026 23:42:51.179 * Module 'testkeyspace' loaded from /work/tests/modules/keyspace_events.so
    14:M 01 Oct 2026 23:42:51.180 * Server initialized
    14:M 01 Oct 2026 23:42:51.180 * Ready to accept connections tcp
    VERIFY_EXIT=0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
