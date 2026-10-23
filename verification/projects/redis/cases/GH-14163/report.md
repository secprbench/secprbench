# Verification report: pr_review_GH-14163

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: NullPointerDereference
- **Intro commit**: `aa856b39f2ca65dbcc0eaae2d2c52f7a35291bbf`
- **Intro parent**: `9f30dd03cd136eda00f5eb82f28f503452fdd11a`
- **Fix commit**: `4322cebc1764d433b3fce3b3a108252648bf59e7`
- **Affected files**: ['src/script_lua.c']

## PoC
- source: agent-generated (initial source: candidate_only)
- dir: `/research-data/secprbench/season100-balanced-20261001/repair-gh14163-location-v1/verification/cases/redis/3c017bb8faf8033e5c03/attempts/01/pocs/redis/GH-14163`
- input: `None` (0 bytes)
- run.sh: True

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- Root cause: luaExtractErrorInformation() in src/script_lua.c reads the Lua error table's 'err' field and only assigns err_info->msg inside `if (lua_isstring(lua, -1))`, with no else/default branch. When the error table has no 'err' field (as produced by `error({})`), err_info->msg stays NULL. The caller luaCallFunction() then unconditionally passes err_info.msg into sdscatfmt() (called from evalGenericCommand), which calls strlen on it. Using the identical run.sh/command on each revision: pre_intro (parent 9f30dd03cd13) returns a normal Lua error reply ('attempt to concatenate...'), exits 0, shuts down cleanly, no sanitizer report, run_poc reports crashed=False. post_intro (intro commit aa856b39f2ca) crashes: run_poc reports crashed=True, exit=1, and UndefinedBehaviorSanitizer reports 'null pointer passed as argument 1, which is declared to never be null' at sds.c:746 inside sdscatfmt, with stack frames #1 luaCallFunction (script_lua.c:1552) <- #2 evalGenericCommand (eval.c:516) <- #3 evalCommand <- processCommand, exactly the code path named in the root cause; the client connection is dropped. post_benign (companion fix applied on the same base) returns a graceful fallback error ('ERR unknown error script: ...'), exits 0, shuts down cleanly, no sanitizer report, crashed=False - consistent with script_lua.c in that build now having an added else branch `err_info->msg = sdsnew(\"ERR unknown error\")` when 'err' is not a string. This isolates the NULL-pointer-dereference regression to the intro commit and confirms the benign companion removes it, matching the upstream PR's own reproduction (`EVAL error{} 0` crash, redis/redis#14163).

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=9f30dd03cd13  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=4f5d3e7aee8afdfd9025f32043dee4d0b74c48772bdd0e3ab7a1453a39eb3f9c
  source_integrity=True
  output_tail:
    ERR Error running script (call to 5988249b2756086f025661223ac4982a2d1701ec): @err_handler_def:8: err_handler_def:8: attempt to concatenate local 'err' (a table value)
    
    9:C 01 Oct 2026 22:11:23.538 # oO0OoO0OoO0Oo Redis is starting oO0OoO0OoO0Oo
    9:C 01 Oct 2026 22:11:23.538 # Redis version=255.255.255, bits=64, commit=00000000, modified=0, pid=9, just started
    9:C 01 Oct 2026 22:11:23.538 # Configuration loaded
    9:M 01 Oct 2026 22:11:23.540 * monotonic clock: POSIX clock_gettime
    9:M 01 Oct 2026 22:11:23.543 * Running mode=standalone, port=16399.
    9:M 01 Oct 2026 22:11:23.543 # Server initialized
    9:M 01 Oct 2026 22:11:23.543 # WARNING overcommit_memory is set to 0! Background save may fail under low memory condition. To fix this issue add 'vm.overcommit_memory = 1' to /etc/sysctl.conf and then reboot or run the command 'sysctl vm.overcommit_memory=1' for this to take effect.
    9:M 01 Oct 2026 22:11:23.543 * The AOF directory appendonlydir doesn't exist
    9:M 01 Oct 2026 22:11:23.543 * Ready to accept connections
    9:M 01 Oct 2026 22:11:23.758 # User requested shutdown...
    9:M 01 Oct 2026 22:11:23.758 # Redis is now ready to exit, bye bye...
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=1  poc_ran=True  patched=False
  commit=aa856b39f2ca  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=4f5d3e7aee8afdfd9025f32043dee4d0b74c48772bdd0e3ab7a1453a39eb3f9c
  source_integrity=True
  sanitizer:
    memory=1' for this to take effect.
    9:M 01 Oct 2026 22:11:19.687 * The AOF directory appendonlydir doesn't exist
    9:M 01 Oct 2026 22:11:19.688 * Ready to accept connections
    VERIFY_EXIT=1
    
    sds.c:746:44: runtime error: null pointer passed as argument 1, which is declared to never be null
    /usr/include/string.h:408:33: note: nonnull attribute specified here
        #0 0x559d9ea11ec7 in sdscatfmt /work/src/sds.c:746:37
        #1 0x559d9ec6e4ae in luaCallFunction /work/src/script_lua.c:1552:25
        #2 0x559d9eb61c1d in evalGenericCommand /work/src/eval.c:516:5
        #3 0x559d9eb6221d in evalCommand /work/src/eval.c:526:9
        #4 0x559d9e9f5e97 in call /work/src/server.c:3238:5
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=9f30dd03cd13  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=4f5d3e7aee8afdfd9025f32043dee4d0b74c48772bdd0e3ab7a1453a39eb3f9c
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    ERR unknown error script: 5988249b2756086f025661223ac4982a2d1701ec, on @user_script:1.
    
    9:C 01 Oct 2026 22:11:25.497 # oO0OoO0OoO0Oo Redis is starting oO0OoO0OoO0Oo
    9:C 01 Oct 2026 22:11:25.497 # Redis version=255.255.255, bits=64, commit=00000000, modified=0, pid=9, just started
    9:C 01 Oct 2026 22:11:25.497 # Configuration loaded
    9:M 01 Oct 2026 22:11:25.500 * monotonic clock: POSIX clock_gettime
    9:M 01 Oct 2026 22:11:25.502 * Running mode=standalone, port=16399.
    9:M 01 Oct 2026 22:11:25.508 # Server initialized
    9:M 01 Oct 2026 22:11:25.508 # WARNING overcommit_memory is set to 0! Background save may fail under low memory condition. To fix this issue add 'vm.overcommit_memory = 1' to /etc/sysctl.conf and then reboot or run the command 'sysctl vm.overcommit_memory=1' for this to take effect.
    9:M 01 Oct 2026 22:11:25.509 * The AOF directory appendonlydir doesn't exist
    9:M 01 Oct 2026 22:11:25.509 * Ready to accept connections
    9:M 01 Oct 2026 22:11:25.714 # User requested shutdown...
    9:M 01 Oct 2026 22:11:25.714 # Redis is now ready to exit, bye bye...
    VERIFY_EXIT=0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
