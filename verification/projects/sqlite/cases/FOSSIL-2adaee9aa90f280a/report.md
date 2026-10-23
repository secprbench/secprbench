# Verification report: pr_review_FOSSIL-2adaee9aa90f280a

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: OutOfBoundsRead
- **Intro commit**: `e995d2c226e2b65c5e40cd238415bdfeb0936e8c`
- **Intro parent**: `1ffb6be1195c592e6c85d57603984b1f36bfde62`
- **Fix commit**: `288f35685473c82b12bd47610e473ec34524bba7`
- **Affected files**: ['src/expr.c', 'src/vdbeaux.c', 'src/vdbe.c', 'src/pragma.c']

## PoC
- source: agent-generated (initial source: no_poc)
- dir: `/research-data/secprbench/season100-balanced-20261001/verification-v3/cases/sqlite/af1d01b48fc010c92760/attempts/01/pocs/sqlite/FOSSIL-2adaee9aa90f280a`
- input: `poc.sql` (139 bytes)
- run.sh: False

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- Root cause matches meta.json: the 2022 IS NULL/NOT NULL optimization (sqlite3VdbeTypeofColumn / OPFLAG_TYPEOFARG) tags the OP_Column opcode that loads a column into a register so the VDBE only materializes the column's type, not its full content, whenever that register is the immediate target of an IS NULL/NOT NULL test. It does this without checking whether the same register is a shared/cached column register that will later be re-read for its real value by another part of the same CHECK expression. In my PoC, the CHECK constraint `x IS NULL OR length(x) > 0` is recompiled for the UPDATE (UPDATE t SET x=x), forcing the column `x` to be loaded via OP_Column into a cached register that is first consulted for the IS NULL test (tagging the opcode TYPEOFARG, which skips materializing content for the large 200000-byte blob) and then reused by length(x) for the real value, which now contains a bogus/under-loaded length. This corrupted length later drives a memcpy in sqlite3VdbeMemGrow/vdbeMemAddTerminator/sqlite3VdbeMemMakeWriteable that reads far past a small global buffer (sqlite3CtypeMap/sqlite3UpperToLower), i.e., a genuine out-of-bounds read, reported by AddressSanitizer as 'global-buffer-overflow ... READ of size 200000'.
- pre_intro (1ffb6be1195c): script runs cleanly, exit=0, prints '1', no sanitizer report.
- post_intro (e995d2c226e2): same script crashes immediately, exit=134, with a clear AddressSanitizer global-buffer-overflow READ report through sqlite3VdbeMemGrow/vdbeMemAddTerminator/sqlite3VdbeMemMakeWriteable/sqlite3VdbeExec — exactly the code path touched by the intro commit (src/expr.c TK_ISNULL/TK_NOTNULL calling sqlite3VdbeTypeofColumn, and src/vdbeaux.c's new sqlite3VdbeTypeofColumn/vdbe.c OPFLAG_TYPEOFARG handling for OP_Column).
- post_benign (fix applied): identical script runs cleanly again, exit=0, prints '1', no sanitizer report.
The same exact command/input was used unchanged across all three builds, so the pre/post/benign comparison is valid and the OutOfBoundsRead regression is confirmed introduced by e995d2c226e2 and removed by the fix/benign commit.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=1ffb6be1195c  note=build cached
  command=sh -c "/work/sqlite3 /tmp/dbx.db < /poc/poc.sql"
  poc_sha256=fafb7e248ab79d3cfc3170083097aaea4601a2a840aa8720bdc2ae9cd1b9f909
  source_integrity=True
  output_tail:
    1
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=e995d2c226e2  note=build cached
  command=sh -c "/work/sqlite3 /tmp/dbx.db < /poc/poc.sql"
  poc_sha256=fafb7e248ab79d3cfc3170083097aaea4601a2a840aa8720bdc2ae9cd1b9f909
  source_integrity=True
  sanitizer:
    VERIFY_EXIT=134
    
    =================================================================
    ==9==ERROR: AddressSanitizer: global-buffer-overflow on address 0x55ae26359c20 at pc 0x7f633ee4a397 bp 0x7ffc76399480 sp 0x7ffc76398c28
    READ of size 200000 at 0x55ae26359c20 thread T0
        #0 0x7f633ee4a396 in __interceptor_memcpy ../../../../src/libsanitizer/sanitizer_common/sanitizer_common_interceptors.inc:827
        #1 0x55ae26074630 in memcpy /usr/include/x86_64-linux-gnu/bits/string_fortified.h:29
        #2 0x55ae26074630 in sqlite3VdbeMemGrow /work/sqlite3.c:80163
        #3 0x55ae26076b34 in vdbeMemAddTerminator /work/sqlite3.c:80210
        #4 0x55ae26076e2a in sqlite3VdbeMemMakeWriteable /work/sqlite3.c:80233
        #5 0x55ae261efc84 in sqlite3VdbeExec /work/sqlite3.c:91076
        #6 0x55ae2622028c in sqlite3Step /work/sqlite3.c:87938
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=1ffb6be1195c  note=build cached
  command=sh -c "/work/sqlite3 /tmp/dbx.db < /poc/poc.sql"
  poc_sha256=fafb7e248ab79d3cfc3170083097aaea4601a2a840aa8720bdc2ae9cd1b9f909
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    1
    VERIFY_EXIT=0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
