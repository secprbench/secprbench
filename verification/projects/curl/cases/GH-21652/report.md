# Verification report: pr_review_GH-21652

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: LogicError
- **Intro commit**: `831a1514843bfa4d4d006627fb84c06ced8ea700`
- **Intro parent**: `aafbe089a88c42bf81ff8cf868f20263661ad3e4`
- **Fix commit**: `d74c0ada4e317566f19b4fac44d91a9eaa93d2bf`
- **Affected files**: ['lib/urlapi.c']

## PoC
- source: agent-generated (initial source: candidate_only)
- dir: `/research-data/secprbench/season100-20261004-collected133-pipeline-v1/verification/cases/curl/4916d583bc23ebb3161b/attempts/01/pocs/curl/GH-21652`
- input: `None` (0 bytes)
- run.sh: True

## Findings

- Exact bug and unaffected output lines matched the shared three-version Docker replay.
- Root cause confirmed by source inspection and dynamic reproduction via run_poc on all three versions. ipv4_normalize() in lib/urlapi.c parses dot-separated host components; when parsing the 4th component "0x" (hex prefix with no following hex digits), curlx_str_hex returns STRE_NO_NUM with the cursor already at end-of-string. Commit 831a1514843b (intro) added a lenient fallback `if(!n || (rc != STRE_NO_NUM) || *c) return HOST_NAME; n--;` intended only to swallow a genuine trailing dot after the last real IPv4 octet, but this same lenient path is also taken for the hex-prefix-with-no-digits case, since it produces the identical (rc==STRE_NO_NUM, *c=='\\0') signature. As a result a non-IPv4 hostname like "1.2.3.0x" is misclassified as IPv4 and silently renormalized to "1.2.0.3". The fix commit d74c0ada4e31 adds an immediate `if(rc) return HOST_NAME;` right after the curlx_str_hex call (confirmed present in post_benign source, absent in post_intro), rejecting the hex-prefix failure before it can reach the shared lenient-trailing-dot check. pre_intro lacks the lenient trailing-dot feature altogether (any rc failure returns HOST_NAME unconditionally), so "1.2.3.0x" is also correctly left untouched there, for a different reason, matching post_benign's externally observable behavior.

## Agent oracle

- machine gate: verified (behavioral)
- basis: Exact bug and unaffected output lines matched the shared three-version Docker replay.
- bug_marker: "OBSERVATION: host NORMALIZED to [1.2.0.3] (treated as IPv4, BUG)"
- pre_marker: "OBSERVATION: host unchanged (not treated as IPv4)"
- benign_marker: "OBSERVATION: host unchanged (not treated as IPv4)"
- target execution: run_poc(pre_intro): exit=0, output includes "get rc=0 host=[1.2.3.0x]" then "OBSERVATION: host unchanged (not treated as IPv4)". run_poc(post_intro): exit=0, output includes "get rc=0 host=[1.2.0.3]" then "OBSERVATION: host NORMALIZED to [1.2.0.3] (treated as IPv4, BUG)". run_poc(post_benign): exit=0, output includes "get rc=0 host=[1.2.3.0x]" then "OBSERVATION: host unchanged (not treated as IPv4)". Invocation exercises lib/urlapi.c's ipv4_normalize() via the public CURLU API (curl_url_set/curl_url_get on CURLUPART_HOST). Source diff confirmed: post_intro's ipv4_normalize is missing the `if(rc) return HOST_NAME;` guard immediately after the curlx_str_hex() call that is present in post_benign, matching fix commit d74c0ada4e31's content.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=aafbe089a88c  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=70b1606adfdbce4fd49f1a19d21a3bb43b7cc2113faa8177efc2e9c8ff74719a
  source_integrity=True
  output_tail:
    set rc=0
    get rc=0 host=[1.2.3.0x]
    OBSERVATION: host unchanged (not treated as IPv4)
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=831a1514843b  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=70b1606adfdbce4fd49f1a19d21a3bb43b7cc2113faa8177efc2e9c8ff74719a
  source_integrity=True
  output_tail:
    set rc=0
    get rc=0 host=[1.2.0.3]
    OBSERVATION: host NORMALIZED to [1.2.0.3] (treated as IPv4, BUG)
    VERIFY_EXIT=0
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=aafbe089a88c  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=70b1606adfdbce4fd49f1a19d21a3bb43b7cc2113faa8177efc2e9c8ff74719a
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    set rc=0
    get rc=0 host=[1.2.3.0x]
    OBSERVATION: host unchanged (not treated as IPv4)
    VERIFY_EXIT=0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
