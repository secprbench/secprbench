# Verification report: pr_review_GH-18902

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: LogicError
- **Intro commit**: `395365ad2d9a6c3f1a35d5e268a6af2824129832`
- **Intro parent**: `07a3cd83e0456ca17dfd8c3104af7cf45b7a1ff5`
- **Fix commit**: `4bfd7a961521e1fd6aab7610e931d82a342781a8`
- **Affected files**: ['lib/vtls/openssl.c', 'lib/vtls/vtls_int.h']

## PoC
- source: agent-final (initial source: locally_fix_derived)
- dir: `/research-data/secprbench/season100-20261002-new-reports/curl-gh18902-imported-reference-v1/verification-unified28-v1/cases/curl/8b0905a9b5da0239d5f5/attempts/01/pocs/curl/GH-18902`
- input: `ocsp-session.poc` (357 bytes)
- run.sh: True

## Findings

- Exact bug and unaffected output lines matched the shared three-version Docker replay.
- Root cause matches: the intro commit adds a `connssl->reused_session` check that skips verifystatus() on session resumption, while ossl_connect_step1 can still offer/accept a cached session when CURLOPT_SSL_VERIFYSTATUS is set, so a resumed session's (now revoked) OCSP status is never re-checked. Reproduced with the identical harness (run.sh -> replay.py -> client.c, same fixtures) across all three revisions: pre_intro performs the status check on the resumed session and rejects the revoked status (SECOND_RESULT=91, exact oracle line "ORACLE_RESULT=PROTECTED_REVOKED_OCSP_REJECTED", exit 0); post_intro resumes the session ("SSL reusing session ID"), completely skips the OCSP status check (no "SSL certificate status" line at all in its log), and accepts the revoked certificate (SECOND_RESULT=0, exact oracle line "ORACLE_RESULT=VULNERABLE_OCSP_VALIDATION_BYPASS", exit 1); post_benign (one-line companion fix forcing a full handshake when sessionid && verifystatus) forces a fresh handshake ("old SSL session ID is stale, removing"), correctly detects and rejects the revoked status ("SSL certificate status: revoked (1)", SECOND_RESULT=91, exact oracle line "ORACLE_RESULT=PROTECTED_REVOKED_OCSP_REJECTED", exit 0). This is a pure logic bug (no sanitizer/crash); the oracle is self-checking and deterministic, matching the fast-path exit codes (0/1/0), and the full logs confirm the mechanism (session reuse enabling a skipped status check) rather than an unrelated failure.

## Agent oracle

- machine gate: verified (behavioral)
- basis: Exact bug and unaffected output lines matched the shared three-version Docker replay.
- bug_marker: "ORACLE_RESULT=VULNERABLE_OCSP_VALIDATION_BYPASS"
- pre_marker: "ORACLE_RESULT=PROTECTED_REVOKED_OCSP_REJECTED"
- benign_marker: "ORACLE_RESULT=PROTECTED_REVOKED_OCSP_REJECTED"
- target execution: run_poc outputs for all three builds: pre_intro exit=0, log shows "SECOND_RESULT=91 SSL server certificate status verification FAILED" then "ORACLE_RESULT=PROTECTED_REVOKED_OCSP_REJECTED"; post_intro exit=1, log shows "SSL reusing session ID" then "SECOND_RESULT=0 No error" (no status check performed) then "ORACLE_RESULT=VULNERABLE_OCSP_VALIDATION_BYPASS"; post_benign exit=0, log shows "old SSL session ID is stale, removing" then "SSL certificate status: revoked (1)" then "SECOND_RESULT=91 SSL server certificate status verification FAILED" then "ORACLE_RESULT=PROTECTED_REVOKED_OCSP_REJECTED".

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=07a3cd83e045  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=1b5f791f01b34731e419b9a8d03771bbd6781ee9f45dc4f64dd85182b0dbea5c
  source_integrity=True
  output_tail:
    * SSL reusing session ID
    *  CAfile: /poc/ca.crt
    *  CApath: /etc/ssl/certs
    * SSL connection using TLSv1.2 / ECDHE-RSA-AES256-GCM-SHA384 / X25519 / UNDEF
    * ALPN: server did not agree on a protocol. Uses default.
    * Server certificate:
    *  subject: CN=localhost
    *  start date: Oct  2 16:30:09 2026 GMT
    *  expire date: Dec 31 16:30:09 2026 GMT
    *  subjectAltName: host "localhost" matched cert's "localhost"
    *  issuer: CN=SecPRBench Local CA
    *  SSL certificate verify ok.
    * No OCSP response received
    * Closing connection
    SECOND_RESULT=91 SSL server certificate status verification FAILED
    
    ORACLE_CLIENT_LOG_END
    ORACLE_RESULT=PROTECTED_REVOKED_OCSP_REJECTED
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=1  poc_ran=True  patched=False
  commit=395365ad2d9a  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=1b5f791f01b34731e419b9a8d03771bbd6781ee9f45dc4f64dd85182b0dbea5c
  source_integrity=True
  output_tail:
    * SSL reusing session ID
    *  CAfile: /poc/ca.crt
    *  CApath: /etc/ssl/certs
    * SSL connection using TLSv1.2 / ECDHE-RSA-AES256-GCM-SHA384 / X25519 / UNDEF
    * ALPN: server did not agree on a protocol. Uses default.
    * Server certificate:
    *  subject: CN=localhost
    *  start date: Oct  2 16:30:09 2026 GMT
    *  expire date: Dec 31 16:30:09 2026 GMT
    *  subjectAltName: host "localhost" matched cert's "localhost"
    *  issuer: CN=SecPRBench Local CA
    *  SSL certificate verify ok.
    * using HTTP/1.x
    * Closing connection
    SECOND_RESULT=0 No error
    
    ORACLE_CLIENT_LOG_END
    ORACLE_RESULT=VULNERABLE_OCSP_VALIDATION_BYPASS
    VERIFY_EXIT=1
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=07a3cd83e045  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=1b5f791f01b34731e419b9a8d03771bbd6781ee9f45dc4f64dd85182b0dbea5c
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    * SSL connection using TLSv1.2 / ECDHE-RSA-AES256-GCM-SHA384 / X25519 / RSASSA-PSS
    * ALPN: server did not agree on a protocol. Uses default.
    * Server certificate:
    *  subject: CN=localhost
    *  start date: Oct  2 16:30:09 2026 GMT
    *  expire date: Dec 31 16:30:09 2026 GMT
    *  subjectAltName: host "localhost" matched cert's "localhost"
    *  issuer: CN=SecPRBench Local CA
    *  SSL certificate verify ok.
    *   Certificate level 0: Public key type RSA (2048/112 Bits/secBits), signed using sha256WithRSAEncryption
    *   Certificate level 1: Public key type RSA (2048/112 Bits/secBits), signed using sha256WithRSAEncryption
    * SSL certificate status: revoked (1)
    * SSL certificate revocation reason: (UNKNOWN) (-1)
    * Closing connection
    SECOND_RESULT=91 SSL server certificate status verification FAILED
    
    ORACLE_CLIENT_LOG_END
    ORACLE_RESULT=PROTECTED_REVOKED_OCSP_REJECTED
    VERIFY_EXIT=0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
