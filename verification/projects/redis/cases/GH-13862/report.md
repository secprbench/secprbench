# Verification report: pr_review_GH-13862

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: LogicError
- **Intro commit**: `47579bdf5cccfbac1cf2b6e7e52218c5b9faed86`
- **Intro parent**: `b02780c41dbc5b28d265b5cf141c03c1a7383ef9`
- **Fix commit**: `427c36888e1a0896dbbc830873ac6935a8019d41`
- **Affected files**: ['src/db.c']

## PoC
- source: agent-generated (initial source: candidate_only)
- dir: `/research-data/secprbench/season100-20261002-repairs/redis-gh13862-reference-import-v2/verification/cases/redis/42def1da09d1d4321728/attempts/01/pocs/redis/GH-13862`
- input: `None` (0 bytes)
- run.sh: True

## Findings

- Exact bug and unaffected output lines matched the shared three-version Docker replay.
- The intro commit (47579bdf5ccc) broke the invariant documented in dbRandomKey()'s retry-loop guard ("the only way expireIfNeeded() can refuse to delete an expired key without eventually returning 0 is if this is a replica") by adding a second, primary-side path (client-pause-driven write/expire suppression) where expireIfNeeded() also refuses to delete, without updating the dbRandomKey() maxtries safety-valve condition to cover it. Reproduced exactly the upstream report/PR test: on a primary with CLIENT PAUSE ... WRITE active and the only key in the DB logically expired, RANDOMKEY spins forever re-picking the same expired key, burning 100% CPU and never responding. post_intro hangs (timeout/RC=124) under the identical command sequence that pre_intro and post_benign (fix 427c36888e1a's companion) both complete normally and promptly (RC=0). The only environment accommodation made was relinking against a UB-fixed recompile of the unrelated, pre-existing-buggy vendored sha256.c (used only for run_id/hash-seed entropy at startup) so the server could even boot under this sanitizer configuration; the labelled file (src/db.c) and its logic were left completely untouched and identical to each revision's normal build.

## Agent oracle

- machine gate: verified (behavioral)
- basis: Exact bug and unaffected output lines matched the shared three-version Docker replay.
- bug_marker: "RANDOMKEY_HUNG_INFINITE_LOOP"
- pre_marker: "RANDOMKEY_RETURNED_OK"
- benign_marker: "RANDOMKEY_RETURNED_OK"
- target execution: Invocation run across pre_intro(b02780c41dbc)/post_intro(47579bdf5ccc)/post_benign: build each revision's normal object tree via the harness's build_version, then (in run.sh, executed identically for all three versions) relink a redis-server binary substituting only the vendored sha256.o (unrelated to db.c / the labelled bug) for a cast-fixed recompile of the identical algorithm from the same sha256.c source (/poc/sha256_fixed.c, only difference: `(WORD)data[j] << 24` instead of `data[j] << 24`), to get past an unrelated, pre-existing UBSan abort (sha256.c:49 signed-left-shift of a byte with the top bit set, hit by getRandomBytes() at startup on literally every redis-server launch in this -fsanitize=undefined -fno-sanitize-recover=all build, independent of version/target bug, confirmed via direct docker_shell experiments showing the crash, no correlation to the labelled bug, and LD_PRELOAD interposition failing to help since it's an intra-binary call). No tracked source file was edited; src/db.c (the actual affected file) and every other object are linked completely unmodified from each version's existing build. With the server up, ran: SET key value PX 50; CLIENT PAUSE 10000 WRITE; sleep 0.3s (key now logically expired); `timeout 5 redis-cli randomkey`.
- pre_intro (b02780c41dbc): randomkey exit code 0, prints key promptly, server shuts down cleanly afterward -> line `RANDOMKEY_RETURNED_OK`.
- post_intro (47579bdf5ccc): randomkey times out (exit code 124), redis-cli hangs the full 5s; the server process pegs a CPU core in dbRandomKey()'s while(1) retry loop and never services the client-pause/unpause or shutdown commands afterward (had to pkill -9) -> line `RANDOMKEY_HUNG_INFINITE_LOOP`, matching the reported "CPU utilization reaches 100%, server unavailable".
- post_benign: randomkey exit code 0, same as pre_intro, graceful shutdown -> line `RANDOMKEY_RETURNED_OK`.
Same exact command/input sequence (run.sh) used verbatim for all three.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=b02780c41dbc  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=e0ef47e89887990a6c3c576f51b355ec1277b449be870af648658bb90bcc64c1
  source_integrity=True
  output_tail:
    + grep -q PONG
    + break
    + /work/src/redis-cli -p 7777 flushall
    + /work/src/redis-cli -p 7777 set key value px 50
    + /work/src/redis-cli -p 7777 client pause 10000 write
    + sleep 0.3
    + echo '=== calling randomkey with 5s timeout ==='
    + timeout 5 /work/src/redis-cli -p 7777 randomkey
    + RC=0
    + echo 'randomkey exit code: 0'
    + '[' 0 -eq 124 ']'
    + echo RANDOMKEY_RETURNED_OK
    + timeout 2 /work/src/redis-cli -p 7777 client unpause
    + timeout 2 /work/src/redis-cli -p 7777 shutdown nosave
    + sleep 0.3
    + pkill -9 -f redis-server-fixed
    + sleep 0.2
    + echo '---server log tail---'
    + tail -20 /tmp/rsf.log
    + exit 0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=47579bdf5ccc  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=e0ef47e89887990a6c3c576f51b355ec1277b449be870af648658bb90bcc64c1
  source_integrity=True
  output_tail:
    + grep -q PONG
    + break
    + /work/src/redis-cli -p 7777 flushall
    + /work/src/redis-cli -p 7777 set key value px 50
    + /work/src/redis-cli -p 7777 client pause 10000 write
    + sleep 0.3
    + echo '=== calling randomkey with 5s timeout ==='
    + timeout 5 /work/src/redis-cli -p 7777 randomkey
    + RC=124
    + echo 'randomkey exit code: 124'
    + '[' 124 -eq 124 ']'
    + echo RANDOMKEY_HUNG_INFINITE_LOOP
    + timeout 2 /work/src/redis-cli -p 7777 client unpause
    + timeout 2 /work/src/redis-cli -p 7777 shutdown nosave
    + sleep 0.3
    + pkill -9 -f redis-server-fixed
    + sleep 0.2
    + echo '---server log tail---'
    + tail -20 /tmp/rsf.log
    + exit 0
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=b02780c41dbc  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=e0ef47e89887990a6c3c576f51b355ec1277b449be870af648658bb90bcc64c1
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    + grep -q PONG
    + break
    + /work/src/redis-cli -p 7777 flushall
    + /work/src/redis-cli -p 7777 set key value px 50
    + /work/src/redis-cli -p 7777 client pause 10000 write
    + sleep 0.3
    + echo '=== calling randomkey with 5s timeout ==='
    + timeout 5 /work/src/redis-cli -p 7777 randomkey
    + RC=0
    + echo 'randomkey exit code: 0'
    + '[' 0 -eq 124 ']'
    + echo RANDOMKEY_RETURNED_OK
    + timeout 2 /work/src/redis-cli -p 7777 client unpause
    + timeout 2 /work/src/redis-cli -p 7777 shutdown nosave
    + sleep 0.3
    + pkill -9 -f redis-server-fixed
    + sleep 0.2
    + echo '---server log tail---'
    + tail -20 /tmp/rsf.log
    + exit 0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
