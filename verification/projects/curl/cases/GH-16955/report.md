# Verification report: pr_review_GH-16955

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: LogicError
- **Intro commit**: `f78700814d702c523a7a2c3766a1ca60f3db7edc`
- **Intro parent**: `279a4772ae67dd4d9770e11e60040f9113b1c345`
- **Fix commit**: `5fbd78eb2dc4afbd8884e8eed27147fc3d4318f6`
- **Affected files**: ['lib/http2.c']

## PoC
- source: agent-final (initial source: reporter_adapted_public_poc)
- dir: `/research-data/secprbench/curl-gh16955-normal-v1/verification/cases/curl/c8e24dc45292c8d993f8/attempts/01/pocs/curl/GH-16955`
- input: `input.poc` (140 bytes)
- run.sh: True

## Findings

- Exact bug and unaffected output lines matched the shared three-version Docker replay.
- Same run.sh / same client+server/classify oracle executed unmodified against all three builds. pre_intro (279a4772ae67) and post_benign (fix 5fbd78eb2dc4 applied) both complete the full 16MiB transfer with peer window restored to 4194304 and 3 stream WINDOW_UPDATEs (ORACLE_RESULT=FULL_16M_RESPONSE, exit 0). post_intro (f78700814d70) stalls permanently after only 10485760 of 16777216 bytes with peer window stuck at 0 and only 1 WINDOW_UPDATE ever sent (ORACLE_RESULT=WINDOW_STALL_10M_ZERO_WINDOW_NO_UPDATE, exit 1), i.e. the HTTP/2 receive-window deadlock after pause/unpause described in GH-16955 and meta.json's root cause (write_paused bridge shrinks the local window to zero; on unpause the window-update submission omits the nghttp2 internal local-window setter call, so the stream never recovers). This is a clean behavioral reproduction: identical invocation, divergent outcome only in post_intro, restored in post_benign.

## Agent oracle

- machine gate: verified (behavioral)
- basis: Exact bug and unaffected output lines matched the shared three-version Docker replay.
- bug_marker: "ORACLE_RESULT=WINDOW_STALL_10M_ZERO_WINDOW_NO_UPDATE"
- pre_marker: "ORACLE_RESULT=FULL_16M_RESPONSE"
- benign_marker: "ORACLE_RESULT=FULL_16M_RESPONSE"
- target execution: pre_intro: ORACLE_TARGET_SLOW_BYTES=16777216 ORACLE_PEER_WINDOW=4194304 ORACLE_STREAM_WINDOW_UPDATES=3 ORACLE_RESULT=FULL_16M_RESPONSE VERIFY_EXIT=0 | post_intro: ORACLE_TARGET_SLOW_BYTES=10485760 ORACLE_PEER_WINDOW=0 ORACLE_STREAM_WINDOW_UPDATES=1 ORACLE_RESULT=WINDOW_STALL_10M_ZERO_WINDOW_NO_UPDATE VERIFY_EXIT=1 | post_benign: ORACLE_TARGET_SLOW_BYTES=16777216 ORACLE_PEER_WINDOW=4194304 ORACLE_STREAM_WINDOW_UPDATES=3 ORACLE_RESULT=FULL_16M_RESPONSE VERIFY_EXIT=0

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=279a4772ae67  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=79fb24fe8b38977b46685b94077fe01845a9aa5755d6e0d6efaf061cce94e536
  source_integrity=True
  output_tail:
    ORACLE_TARGET_SLOW_BYTES=16777216
    ORACLE_PEER_WINDOW=4194304
    ORACLE_STREAM_WINDOW_UPDATES=3
    ORACLE_RESULT=FULL_16M_RESPONSE
    VERIFY_EXIT=0
    
    /poc/reporter_adapted.cc: In lambda function:
    /poc/reporter_adapted.cc:565:20: warning: compound assignment with 'volatile'-qualified left operand is deprecated [-Wvolatile]
      565 |             recvd1 += a->read(c, sizeof(c));
          |             ~~~~~~~^~~~~~~~~~~~~~~~~~~~~~~~
    /poc/reporter_adapted.cc: In lambda function:
    /poc/reporter_adapted.cc:571:20: warning: compound assignment with 'volatile'-qualified left operand is deprecated [-Wvolatile]
      571 |             recvd2 += b->read(c, sizeof(c));
          |             ~~~~~~~^~~~~~~~~~~~~~~~~~~~~~~~
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=1  poc_ran=True  patched=False
  commit=f78700814d70  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=79fb24fe8b38977b46685b94077fe01845a9aa5755d6e0d6efaf061cce94e536
  source_integrity=True
  output_tail:
    ORACLE_TARGET_SLOW_BYTES=10485760
    ORACLE_PEER_WINDOW=0
    ORACLE_STREAM_WINDOW_UPDATES=1
    ORACLE_RESULT=WINDOW_STALL_10M_ZERO_WINDOW_NO_UPDATE
    VERIFY_EXIT=1
    
    /poc/reporter_adapted.cc: In lambda function:
    /poc/reporter_adapted.cc:565:20: warning: compound assignment with 'volatile'-qualified left operand is deprecated [-Wvolatile]
      565 |             recvd1 += a->read(c, sizeof(c));
          |             ~~~~~~~^~~~~~~~~~~~~~~~~~~~~~~~
    /poc/reporter_adapted.cc: In lambda function:
    /poc/reporter_adapted.cc:571:20: warning: compound assignment with 'volatile'-qualified left operand is deprecated [-Wvolatile]
      571 |             recvd2 += b->read(c, sizeof(c));
          |             ~~~~~~~^~~~~~~~~~~~~~~~~~~~~~~~
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=279a4772ae67  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=79fb24fe8b38977b46685b94077fe01845a9aa5755d6e0d6efaf061cce94e536
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    ORACLE_TARGET_SLOW_BYTES=16777216
    ORACLE_PEER_WINDOW=4194304
    ORACLE_STREAM_WINDOW_UPDATES=3
    ORACLE_RESULT=FULL_16M_RESPONSE
    VERIFY_EXIT=0
    
    /poc/reporter_adapted.cc: In lambda function:
    /poc/reporter_adapted.cc:565:20: warning: compound assignment with 'volatile'-qualified left operand is deprecated [-Wvolatile]
      565 |             recvd1 += a->read(c, sizeof(c));
          |             ~~~~~~~^~~~~~~~~~~~~~~~~~~~~~~~
    /poc/reporter_adapted.cc: In lambda function:
    /poc/reporter_adapted.cc:571:20: warning: compound assignment with 'volatile'-qualified left operand is deprecated [-Wvolatile]
      571 |             recvd2 += b->read(c, sizeof(c));
          |             ~~~~~~~^~~~~~~~~~~~~~~~~~~~~~~~
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
