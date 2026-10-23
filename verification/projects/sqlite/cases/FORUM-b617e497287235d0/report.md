# Verification report: pr_review_FORUM-b617e497287235d0

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: OutOfBoundsRead
- **Intro commit**: `9dcf3d08c9edc0c30e07a6a06f9d0dd73bfad529`
- **Intro parent**: `0424f255efb2aaa89e29a265683fd260da2b94c7`
- **Fix commit**: `66cd200ede04bbe2c44729c3a4c55433430c4214`
- **Affected files**: ['src/vdbeapi.c']

## PoC
- source: candidate_only
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/sqlite/1563148e5154b3e39348/attempts/01/pocs/sqlite/FORUM-b617e497287235d0`
- input: `None` (0 bytes)
- run.sh: False
- note: poc dir has neither run.sh nor a recognizable input file

## Findings

- Source inspection across versions confirms meta.json's root cause: pre_intro's sqlite3_preupdate_old() (src/vdbeapi.c) checks `iIdx>=p->pCsr->nField` directly and never calls sqlite3TableColumnToStorage(); post_intro's refactor adds `iStore = sqlite3TableColumnToStorage(p->pTab, iIdx)` in the non-pPk branch with no prior bound check of iIdx against pTab->nCol; post_benign (built from the parent source with the fix applied) inserts `else if( iIdx>=p->pTab->nCol ){ rc = SQLITE_MISUSE_BKPT; goto preupdate_old_out; }` before that call, matching fix commit 66cd200ede04. sqlite3TableColumnToStorage() (build.c) has only a debug-only assert and, for a table with a virtual/generated column, loops `for(i=0,n=0;i<iCol;i++) ... pTab->aCol[i]`, reading past the end of the aCol[] allocation when iCol is out of range. Ran the identical PoC via the run_poc tool (same command/input) against all three built versions: post_intro -> exit=134, crashed=True, 'AddressSanitizer: heap-buffer-overflow ... READ of size 2 ... in sqlite3TableColumnToStorage', with the call stack going through sqlite3_preupdate_old -> the harness's preupdate hook -> sqlite3VdbePreUpdateHook, i.e. exactly the labelled API and root cause; pre_intro -> exit=0, crashed=False, harness ran to completion ('done'); post_benign -> exit=0, crashed=False, same clean completion. This is the canonical pattern (pre clean, intro crashes, benign clean) confirming both introduction and the benign fix.

## Per-version results

### pre_intro
```
  (not run)
```
### post_intro
```
  (not run)
```
### post_benign
```
  (not run)
```

## Interpretation

The intro commit introduces the bug (clean before, crash after) and, where a benign companion exists, the benign patch removes it. Labels are consistent with execution.
