# Verification report: pr_review_FOSSIL-26f39ac806a5582f

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: LogicError
- **Intro commit**: `4b136ed70a1eb656efca8cc4079e515d6fc33dd6`
- **Intro parent**: `a11499a1566f3e4b351550462e5b2ea7f1e15a82`
- **Fix commit**: `add73c831bfe86288839f6053b7fcc7adfa72a87`
- **Affected files**: ['ext/fts3/fts3.c', 'ext/fts3/fts3Int.h', 'ext/fts3/fts3_write.c', 'src/delete.c', 'src/expr.c', 'src/select.c', 'src/sqlite.h.in', 'src/vdbe.h']

## PoC
- source: agent-generated (initial source: candidate_only)
- dir: `/research-data/secprbench/season100-balanced-20261001/verification/cases/sqlite/914191dcbc9a47f6f80d/attempts/01/pocs/sqlite/FOSSIL-26f39ac806a5582f`
- input: `None` (0 bytes)
- run.sh: True

## Findings

- Exact bug and unaffected output lines matched the shared three-version Docker replay.
- Root cause: commit 4b136ed70a1e marks the FTS3/4 virtual table module SQLITE_VTAB_INNOCUOUS (fts3DeclareVtab in ext/fts3/fts3.c), lowering its eVtabRisk from SQLITE_VTABRISK_Normal(1) to Low(0). This is checked by vtabIsReadOnly() in src/delete.c (applied when pParse->pToplevel!=0, i.e. inside a trigger) and by the fromDDL gate in src/select.c, both comparing "pTab->u.vtab.p->eVtabRisk" against "(db->flags & SQLITE_TrustedSchema)!=0". Before the change, any nested (triggered) write to an FTS3/4 table was refused outright when trusted_schema=OFF, because eVtabRisk(1) > trustedSchema(0). After the change, eVtabRisk(0) is no longer greater than 0, so the nested write is allowed to proceed into FTS4's own xUpdate, which internally calls sqlite3_prepare_v2() on a dynamically built "SELECT <funcname>(?)" statement using the schema-supplied compress=/uncompress= function name. That internally generated statement is indistinguishable from ordinary trusted top-level SQL and is not flagged as derived from DDL, so the "disallow unsafe SQL functions" check silently does not apply to it, letting a non-innocuous application function run even though trusted_schema=OFF was supposed to prevent exactly that in untrusted/nested schema contexts. The companion fix commit (add73c831bfe, mirroring upstream check-in 26f39ac806 which adds the SQLITE_PREPARE_FROM_DDL flag) propagates the DDL/untrusted-origin context into these internally-generated FTS3/4 statements so the unsafe-function check correctly applies to them.

Verified by direct reproduction in Docker (ASan/UBSan build) using the identical PoC/command across all three revisions:
- pre_intro (commit a11499a1566f, FTS3 NOT yet innocuous): the nested trigger-INSERT into the FTS4 table is refused outright with "unsafe use of virtual table \"f1\"" before ever reaching the compress function; the exact output line "RESULT: rc=1 myfunc_invoked=0" is printed. Bug not present/not reachable — behaves safely.
- post_intro (commit 4b136ed70a1e, FTS3 marked SQLITE_VTAB_INNOCUOUS): the nested write succeeds and the untrusted application function myfunc() is actually invoked via the compress hook despite trusted_schema=OFF; the exact output line "RESULT: rc=0 myfunc_invoked=1" is printed (this line/behavior never appears in pre_intro or post_benign). This is the labelled logic-error/security-check bypass, reproduced live.
- post_benign (fix commit, composed via agent to match upstream add73c831bfe/26f39ac806): the nested write is blocked again with "SQL logic error" (the unsafe-function check now correctly fires on the internally generated compress statement); the exact output line "RESULT: rc=1 myfunc_invoked=0" is printed again, matching pre_intro. Bug is fixed.

The same exact PoC/command was used unmodified across all three builds, and the result cleanly differs: safe -> bug -> fixed, satisfying the required behavioral oracle for a LogicError-class protection bypass.

## Agent oracle

- machine gate: verified (behavioral)
- basis: Exact bug and unaffected output lines matched the shared three-version Docker replay.
- bug_marker: "RESULT: rc=0 myfunc_invoked=1"
- pre_marker: "RESULT: rc=1 myfunc_invoked=0"
- benign_marker: "RESULT: rc=1 myfunc_invoked=0"
- target execution: Confirmed via grep that post_intro's ext/fts3/fts3.c contains `sqlite3_vtab_config(p->db, SQLITE_VTAB_INNOCUOUS);` in fts3DeclareVtab while pre_intro does not. Confirmed the enforcement code paths in src/delete.c (vtabIsReadOnly, checked when pParse->pToplevel!=0, i.e. inside triggers) and src/select.c (fromDDL gate), both comparing `pTab->u.vtab.p->eVtabRisk` against `(db->flags & SQLITE_TrustedSchema)!=0`, matching SQLITE_VTABRISK_Normal=1/Low=0/High=2 constants in sqliteInt.h. This matches the official upstream disclosure (sqlite.org check-in 26f39ac806) and the saved regression tests (evidence/test_01_..._fts3comp1.test section 3, and test_02_..._fts4content.test section 13) which test the same unsafe-function-via-untrusted-schema class of bug for FTS3/4. Full run outputs captured via run_poc for pre_intro, post_intro, and post_benign with the identical poc.c/run.sh.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=a11499a1566f  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=7f04233c2e98e2c43350cfc7d922ba00abd972be225be414f837d9dfd4be3ad9
  source_integrity=True
  output_tail:
    CREATE src -> rc=0 err=(none)
    CREATE f1 -> rc=0 err=(none)
    CREATE TRIGGER tr1 -> rc=0 err=(none)
    PRAGMA trusted_schema=OFF -> rc=0 err=(none)
    INSERT INTO src (fires trigger -> nested INSERT INTO f1) -> rc=1 err=unsafe use of virtual table "f1"
    RESULT: rc=1 myfunc_invoked=0
    PROTECTED_OR_BLOCKED: myfunc never invoked (rc=1)
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=4b136ed70a1e  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=7f04233c2e98e2c43350cfc7d922ba00abd972be225be414f837d9dfd4be3ad9
  source_integrity=True
  output_tail:
    CREATE src -> rc=0 err=(none)
    CREATE f1 -> rc=0 err=(none)
    CREATE TRIGGER tr1 -> rc=0 err=(none)
    PRAGMA trusted_schema=OFF -> rc=0 err=(none)
    INSERT INTO src (fires trigger -> nested INSERT INTO f1) -> rc=0 err=(none)
    RESULT: rc=0 myfunc_invoked=1
    BUG_OBSERVED: trigger-nested write to FTS4 table invoked unsafe myfunc() compress hook despite trusted_schema=OFF
    VERIFY_EXIT=0
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=a11499a1566f  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=7f04233c2e98e2c43350cfc7d922ba00abd972be225be414f837d9dfd4be3ad9
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    CREATE src -> rc=0 err=(none)
    CREATE f1 -> rc=0 err=(none)
    CREATE TRIGGER tr1 -> rc=0 err=(none)
    PRAGMA trusted_schema=OFF -> rc=0 err=(none)
    INSERT INTO src (fires trigger -> nested INSERT INTO f1) -> rc=1 err=SQL logic error
    RESULT: rc=1 myfunc_invoked=0
    PROTECTED_OR_BLOCKED: myfunc never invoked (rc=1)
    VERIFY_EXIT=0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
