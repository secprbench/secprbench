# Verification report: pr_review_GH-28221

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: NullPointerDereference
- **Intro commit**: `cccdf41010d0859a0d134ac45be7218d9ffd90d2`
- **Intro parent**: `ba6f115ccfbb63fbeb2bc8df3c07918a7a59a186`
- **Fix commit**: `24f72a5aaab0243c136e1402b54348fda9cdbc36`
- **Affected files**: ['crypto/x509/v3_attrdesc.c']

## PoC
- source: agent-generated (initial source: incomplete)
- dir: `/research-data/secprbench/season100-afterstage-20261001/repair-openssl-GH-28221-v1/verification/cases/openssl/475898944c14984cdfbb/attempts/01/pocs/openssl/GH-28221`
- input: `crl.der` (200 bytes)
- run.sh: True

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- The intro commit (cccdf41010d0) adds the attributeDescriptor X.509v3 extension support (OSSL_ATTRIBUTE_DESCRIPTOR/OSSL_HASH and i2r_HASH), where i2r_HASH unconditionally dereferenced hash->hashValue->data/length even though hashValue is ASN1_OPT (optional) in the OSSL_HASH ASN.1 template -- so a CRL/certificate whose hashValue is omitted causes a NULL dereference when printed. Reproduced precisely using the project's own oss-fuzz harness (fuzz/crl-test, which is exactly what the reporter used: d2i_X509_CRL + X509_CRL_print) fed the identical crafted, validly-signed CRL DER file across all three versions. post_intro aborts (SIGABRT) with a UBSan 'member access within null pointer of type ASN1_BIT_STRING' report at v3_attrdesc.c:88 inside i2r_HASH, with a call stack running through X509_CRL_print -> X509V3_extensions_print -> X509V3_EXT_print, matching the original issue's own before/after transcript. post_benign (the upstream fix/benign companion), run with the exact same input and command, completes cleanly (exit 0) because the fix adds an explicit `hash->hashValue == NULL` check before the dereference. pre_intro completes cleanly too, but because the entire attributeDescriptor/OSSL_HASH feature (including the vulnerable i2r_HASH) did not exist prior to the intro commit at all -- confirmed separately via a compile-time check showing the relevant types/functions are undeclared in pre_intro's headers -- so the bug is intrinsic to, and wholly introduced by, the intro commit. The same input file and run command were used unmodified across all three versions, satisfying the same-reproducer invariance requirement.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.
- bug_marker: "crypto/x509/v3_attrdesc.c:88:44: runtime error: member access within null pointer of type 'ASN1_BIT_STRING' (aka 'struct asn1_string_st'), stack: i2r_HASH -> i2r_INFO_SYNTAX_POINTER -> i2r_OSSL_INFO_SYNTAX -> i2r_OSSL_PRIVILEGE_POLICY_ID -> i2r_OSSL_ATTRIBUTE_DESCRIPTOR -> X509V3_EXT_print -> X509V3_extensions_print -> X509_CRL_print_ex -> X509_CRL_print -> FuzzerTestOneInput (fuzz/crl.c:32); process SIGABRTs (run_poc reports post_intro: exit=134 crashed=True)."
- pre_marker: "run_poc(pre_intro): exit=0 crashed=False, output \"# /poc/crl.der\" with no sanitizer report -- the attributeDescriptor NID/extension type does not exist in pre_intro at all (it and i2r_HASH were introduced atomically by the intro commit), so the unrecognized extension OID is simply not dispatched to any custom i2r routine and the CRL prints without incident."
- benign_marker: "run_poc(post_benign): exit=0 crashed=False, output \"# /poc/crl.der\" with no sanitizer report -- the fix's added `if (hash->hashValue == NULL) return 0;` guard in i2r_HASH prevents the dereference, so the same CRL prints (truncated at the hash value) without crashing."
- target execution: Using the actual oss-fuzz crl-test binary (/work/fuzz/crl-test, built as part of each version with the project's configured sanitizers) against the identical crafted CRL file /poc/crl.der in all three versions: pre_intro exits 0 cleanly (feature/API did not exist yet, confirmed separately by a compile-time check that the OSSL_ATTRIBUTE_DESCRIPTOR/OSSL_HASH types and i2d_OSSL_ATTRIBUTE_DESCRIPTOR/OSSL_ATTRIBUTE_DESCRIPTOR_free functions used to build this CRL's extension are entirely absent from pre_intro's headers); post_intro aborts (SIGABRT, exit 134) with a UBSan 'member access within null pointer of type ASN1_BIT_STRING' report at v3_attrdesc.c:88 inside i2r_HASH, with a full call stack showing it is reached through the genuine X509_CRL_print extension-printing path exercised by the oss-fuzz crl fuzzer (matching the issue's own before/after transcript almost verbatim, modulo a small line-number shift from local diffs); post_benign exits 0 cleanly with the same input and command, consistent with the fix's explicit NULL check visible in post_benign's v3_attrdesc.c source (`if (hash->hashValue == NULL) return 0;` immediately before the `print_hex(... hash->hashValue->data ...)` call). This is the project's own upstream fix (24f72a5aaab0) and the same reproduction method (fuzz/crl-test test-case) the OpenSSL maintainers themselves used in the GH-28221 report.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=ba6f115ccfbb  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=2a8651e3738d99a9ac83d799c012f5eee3c18c4ebaefd52c6bcf5c124b4f1b16
  source_integrity=True
  output_tail:
    # /poc/crl.der
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=cccdf41010d0  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=2a8651e3738d99a9ac83d799c012f5eee3c18c4ebaefd52c6bcf5c124b4f1b16
  source_integrity=True
  sanitizer:
    # /poc/crl.der
    VERIFY_EXIT=134
    
    crypto/x509/v3_attrdesc.c:88:44: runtime error: member access within null pointer of type 'ASN1_BIT_STRING' (aka 'struct asn1_string_st')
        #0 0x5570e9250ee1 in i2r_HASH /work/crypto/x509/v3_attrdesc.c:88:44
        #1 0x5570e9250ee1 in i2r_INFO_SYNTAX_POINTER /work/crypto/x509/v3_attrdesc.c:104:13
        #2 0x5570e9250ee1 in i2r_OSSL_INFO_SYNTAX /work/crypto/x509/v3_attrdesc.c:126:16
        #3 0x5570e9250ee1 in i2r_OSSL_PRIVILEGE_POLICY_ID /work/crypto/x509/v3_attrdesc.c:146:12
        #4 0x5570e9250ee1 in i2r_OSSL_ATTRIBUTE_DESCRIPTOR /work/crypto/x509/v3_attrdesc.c:178:12
        #5 0x5570e8cbdd1c in X509V3_EXT_print /work/crypto/x509/v3_prn.c:124:14
        #6 0x5570e8cbe07e in X509V3_extensions_print /work/crypto/x509/v3_prn.c:169:14
        #7 0x5570e8cbafcb in X509_CRL_print_ex /work/crypto/x509/t_crl.c:70:5
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=ba6f115ccfbb  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=2a8651e3738d99a9ac83d799c012f5eee3c18c4ebaefd52c6bcf5c124b4f1b16
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    # /poc/crl.der
    VERIFY_EXIT=0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
