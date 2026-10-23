# Verification report: pr_review_GH-20958

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: LogicError
- **Intro commit**: `769ccb4d4261a75c8a4236fbe7dc3e27956db1c9`
- **Intro parent**: `990a23bb97915567415d5857ee6d862a1528f1af`
- **Fix commit**: `ae09e5bf0d1f868f7094be8f640ec46d66e668bf`
- **Affected files**: ['lib/curl_get_line.c']

## PoC
- source: agent-generated (initial source: no_poc)
- dir: `/research-data/secprbench/season100-balanced-20261001/verification/cases/curl/ac1aa8831478c1c85c93/attempts/01/pocs/curl/GH-20958`
- input: `None` (0 bytes)
- run.sh: True

## Findings

- Exact bug and unaffected output lines matched the shared three-version Docker replay.
- root cause confirmed by source diff and by execution. post_intro's Curl_get_line() (commit 769ccb4d4261) only sets `*eof = feof(input)` after fgets() fails and keeps looping `while(1)` until `*eof` is true; with a persistent I/O error (fgets() returns NULL, ferror() true, feof() false forever) the loop never terminates - verified: the PoC hits the 5s alarm guard and prints TIMEOUT_HANG, i.e. a genuine unbounded hang (DoS), not a resource-limit artifact. pre_intro uses the older Curl_get_line(buf,input) implementation which, on fgets() returning NULL with an empty accumulated buffer, falls into the `else` branch and `break`s out of the loop immediately, returning 0 - no hang, confirming the bug is absent before the introducing commit. post_benign (the agent-composed companion fix) adds the same `if(!b && ferror(input)) return CURLE_READ_ERROR;` check as the real upstream fix (ae09e5bf0d1f) and the PoC returns promptly with RESULT=26 (CURLE_READ_ERROR), EOF=0, matching the intended fix behavior. All three revisions were built with ASan+UBSan and exercised with the identical invocation (same run.sh / same FILE* oracle); only the API shape differs across the refactor boundary, which run.sh detects generically from the header rather than from bug-dependent behavior.

## Agent oracle

- machine gate: verified (behavioral)
- basis: Exact bug and unaffected output lines matched the shared three-version Docker replay.
- bug_marker: "TIMEOUT_HANG: Curl_get_line did not return within 5s"
- pre_marker: "RESULT=0 LEN=0"
- benign_marker: "RESULT=26 EOF=0 LEN=0"
- target execution: pre_intro: exit=0, stdout "RESULT=0 LEN=0" (no hang, old implementation bails out). post_intro: process self-terminated via alarm(5) printing "TIMEOUT_HANG: Curl_get_line did not return within 5s" to stderr and exiting 42 (confirmed unbounded loop, i.e. the labelled DoS/infinite-loop logic bug). post_benign: exit=0, stdout "RESULT=26 EOF=0 LEN=0" (CURLE_READ_ERROR returned promptly, no hang) - matches upstream fix ae09e5bf0d1f's added `if(!b && ferror(input)) return CURLE_READ_ERROR;` check, confirmed present verbatim in post_benign's lib/curl_get_line.c.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=990a23bb9791  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=1a3bdd7685765365a4e146e905eedaaa865968e580bbcdc45306840c4d29c3d0
  source_integrity=True
  output_tail:
    /poc/poc_old.c:5: warning: "_GNU_SOURCE" redefined
        5 | #define _GNU_SOURCE
          | 
    <command-line>: note: this is the location of the previous definition
    /poc/poc_old.c: In function 'alarm_handler':
    /poc/poc_old.c:20:3: warning: ignoring return value of 'write' declared with attribute 'warn_unused_result' [-Wunused-result]
       20 |   write(2, msg, sizeof(msg) - 1);
          |   ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    RESULT=0 LEN=0
    EXIT_CODE=0
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=769ccb4d4261  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=1a3bdd7685765365a4e146e905eedaaa865968e580bbcdc45306840c4d29c3d0
  source_integrity=True
  output_tail:
    /poc/poc_new.c:14: warning: "_GNU_SOURCE" redefined
       14 | #define _GNU_SOURCE
          | 
    <command-line>: note: this is the location of the previous definition
    /poc/poc_new.c: In function 'alarm_handler':
    /poc/poc_new.c:29:3: warning: ignoring return value of 'write' declared with attribute 'warn_unused_result' [-Wunused-result]
       29 |   write(2, msg, sizeof(msg) - 1);
          |   ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    EXIT_CODE=42
    VERIFY_EXIT=0
    
    TIMEOUT_HANG: Curl_get_line did not return within 5s
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=990a23bb9791  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=1a3bdd7685765365a4e146e905eedaaa865968e580bbcdc45306840c4d29c3d0
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    /poc/poc_new.c:14: warning: "_GNU_SOURCE" redefined
       14 | #define _GNU_SOURCE
          | 
    <command-line>: note: this is the location of the previous definition
    /poc/poc_new.c: In function 'alarm_handler':
    /poc/poc_new.c:29:3: warning: ignoring return value of 'write' declared with attribute 'warn_unused_result' [-Wunused-result]
       29 |   write(2, msg, sizeof(msg) - 1);
          |   ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    RESULT=26 EOF=0 LEN=0
    EXIT_CODE=0
    VERIFY_EXIT=0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
