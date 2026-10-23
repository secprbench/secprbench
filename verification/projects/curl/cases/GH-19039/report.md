# Verification report: pr_review_GH-19039

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: LogicError
- **Intro commit**: `4cd10ee28b5ee5ad9206c34c2c7887b2ac0cbfd2`
- **Intro parent**: `bc81292ea62cb7141e03d266ef8a50ba66d896bf`
- **Fix commit**: `67c4256f7e4f00d8e85b9a7da0b6004bfe5669e1`
- **Affected files**: ['lib/pop3.c']

## PoC
- source: agent-generated (initial source: no_poc)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/curl/eb094dd72048389196f6/attempts/03/pocs/curl/GH-19039`
- input: `None` (0 bytes)
- run.sh: True

## Findings

- Exact bug and unaffected output lines matched the shared three-version Docker replay.
- meta.json root cause: pop3_perform() (caller) reads data->req.no_body to decide pop3->transfer before calling pop3_perform_command() (callee), which is the function that actually (re)computes data->req.no_body for the command about to be sent. pop3->transfer's only consumer, in pop3_state_command_resp(), decides whether the just-arrived response content is captured as the message body or thrown away.

Built pre_intro (bc81292ea62c), post_intro (4cd10ee28b5e) and post_benign (fix applied on top of pre_intro) and reproduced with an identical fake-server + `curl --head` + RETR-eligible URL scenario in all three, instrumenting the exact decision point with gdb (no target source was modified; gdb only observes live process state).

- post_intro (bug): data->req.no_body is correctly recomputed to 0 ("a body exists", since the outgoing command is RETR, multi-line) by the intro commit's new logic in pop3_perform_command(), but pop3->transfer is stuck at PPTRANSFER_INFO because pop3_perform() decided it earlier using the stale pre-recompute value (1). This exact contradiction between the two fields is the reported bug, and it has a real, concrete consequence: the message body the fake server actually sent ("Hello World", 12 octets) is silently dropped -- curl exits 0 having written 0 bytes even though curl's own (correct) internal no_body state says a body should have been delivered.
- pre_intro: no_body and transfer are both 1 ("no body") at the same observation point -- self-consistent, because pre_intro's pop3_perform_command() has no code path that ever touches data->req.no_body, so the two fields can never disagree in this build (the flaw's precondition -- a second, later recomputation of the same field -- does not exist yet). It also happens to emit 0 bytes for this input, but that is unrelated to the labelled stale-read defect, which structurally cannot manifest without the intro commit's added recompute.
- post_benign: the fix's reordering makes pop3_perform_command() run first, so by the time pop3->transfer is decided, data->req.no_body already holds the fresh, command-aware value (0); transfer and no_body agree (0/PPTRANSFER_BODY), and the real message content is delivered end-to-end (13 bytes, "Hello World\n").

The same /poc/run.sh (default run_poc invocation, no arguments) was used unmodified for all three builds and its output differs exactly as predicted by the root cause: bug_marker appears only in post_intro, pre_intro and post_benign both complete with fields in agreement (for different, non-buggy reasons appropriate to each build's code).

## Agent oracle

- machine gate: verified (behavioral)
- basis: Exact bug and unaffected output lines matched the shared three-version Docker replay.
- bug_marker: "MARKER no_body=0 transfer=1"
- pre_marker: "MARKER no_body=1 transfer=1"
- benign_marker: "MARKER no_body=0 transfer=0"
- target execution: Verbatim run_poc output (default /poc/run.sh) for all three builds (PPTRANSFER_BODY=0 / PPTRANSFER_INFO=1 per lib/pingpong.h):
- pre_intro:   "MARKER no_body=1 transfer=1", "BODY_BYTES=0" -> no_body and transfer both say "no body": self-consistent (pre_intro's pop3_perform_command() never recomputes req.no_body at all, that logic did not exist yet, so the two fields cannot disagree by construction).
- post_intro:  "MARKER no_body=0 transfer=1", "BODY_BYTES=0" -> data->req.no_body has already been correctly recomputed to 0 ("a body is expected", since RETR is multi-line) by pop3_perform_command(), but pop3->transfer is still 1/PPTRANSFER_INFO because pop3_perform() decided it earlier from the stale, pre-recompute value of no_body (1). The two fields contradict each other, and the server's real 12-octet "Hello World" message body is silently discarded (BODY_BYTES=0) even though curl's own state says a body should have been retrieved.
- post_benign: "MARKER no_body=0 transfer=0", "BODY_BYTES=13", BODY_CONTENT="Hello World\n" -> no_body=0 and transfer=0/PPTRANSFER_BODY agree ("body expected"), and the actual message content is delivered.
Source check confirms the mechanism: lib/pop3.c pop3_perform() in post_intro/pre_intro reads data->req.no_body and sets pop3->transfer BEFORE calling pop3_perform_command() (which is the only place, added by intro commit 4cd10ee28b5e, that recomputes data->req.no_body = !pop3_is_multiline(command)); the fix commit 67c4256f7e4f (present in post_benign) reorders pop3_perform() to call pop3_perform_command() first and only then decide pop3->transfer from the now-fresh data->req.no_body.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=bc81292ea62c  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=177cefa9df9fa741b80a34127a57d0ca17e7f4c93cacd1441c33931479607204
  source_integrity=True
  output_tail:
    MARKER no_body=1 transfer=1
    BODY_BYTES=0
    BODY_CONTENT_BEGIN
    
    BODY_CONTENT_END
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=4cd10ee28b5e  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=177cefa9df9fa741b80a34127a57d0ca17e7f4c93cacd1441c33931479607204
  source_integrity=True
  output_tail:
    MARKER no_body=0 transfer=1
    BODY_BYTES=0
    BODY_CONTENT_BEGIN
    
    BODY_CONTENT_END
    VERIFY_EXIT=0
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=bc81292ea62c  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=177cefa9df9fa741b80a34127a57d0ca17e7f4c93cacd1441c33931479607204
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    MARKER no_body=0 transfer=0
    BODY_BYTES=13
    BODY_CONTENT_BEGIN
    Hello World
    
    BODY_CONTENT_END
    VERIFY_EXIT=0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
