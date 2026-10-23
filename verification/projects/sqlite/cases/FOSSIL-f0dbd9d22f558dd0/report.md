# Verification report: pr_review_FOSSIL-f0dbd9d22f558dd0

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: IntegerOverflow
- **Intro commit**: `2ec78c0e4bab11ce288a830c3a13fe34a9224c4a`
- **Intro parent**: `4f2144dac0119044f36de618fae1a5ed24046a3a`
- **Fix commit**: `5b15123fba29709ff32a0aaa13f223223989d369`
- **Affected files**: ['ext/fts5/fts5_main.c']

## PoC
- source: agent-generated (initial source: no_poc)
- dir: `/research-data/secprbench/season100-balanced-20261001/verification/cases/sqlite/cc73137d855c8aa37b6e/attempts/01/pocs/sqlite/FOSSIL-f0dbd9d22f558dd0`
- input: `None` (0 bytes)
- run.sh: False
- note: poc dir has neither run.sh nor a recognizable input file

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- meta.json/discussion.md describe fts5_locale() (ext/fts5/fts5_main.c) computing nBlob = nLocale + 1 + nText in 32-bit 'int' and passing it to sqlite3_malloc(), overflowing when built with an oversize SQLITE_MAX_LENGTH. Verified by building pre_intro, post_intro and post_benign in Docker (project's own ASan+UBSan flags) and, since no PoC existed, crafting a minimal C harness (poc.c) compiled identically (only adding -DSQLITE_ENABLE_FTS5 -DSQLITE_MAX_LENGTH=1200000000 as compile defines, no edits to tracked source) against each revision's own sqlite3.c amalgamation, then running the exact same bound-parameter call via run_poc on all three. post_intro crashes with a UBSan signed-integer-overflow report pinpointing the precise nBlob=nLocale+1+nText line in fts5LocaleFunc. pre_intro lacks the function entirely and exits cleanly (feature/flaw introduced together at the intro commit). post_benign (64-bit arithmetic + malloc64) runs the identical reproducer to clean completion with no sanitizer report, correctly computing the un-overflowed size and safely declining the oversize allocation via SQLite's own allocation-size guard instead of invoking UB. The same reproducing input/command was used unmodified across all three builds.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=4f2144dac011  note=build cached
  command=cd /tmp && cp /work/sqlite3.c . && cp /work/sqlite3.h . && cp /poc/poc.c . && gcc -g -O1 -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer -DSQLITE_CORE -DSQLITE_ENABLE_FTS5 -DSQLITE_MAX_LENGTH=1200000000 -I. -o poc_bin poc.c sqlite3.c -ldl -lpthread -lm && ./poc_bin
  poc_sha256=12841988ff2b8a52a7136ee6e5156d2efbb70ad972e97b648d6ae5dc0e25da63
  source_integrity=True
  output_tail:
    VERIFY_EXIT=0
    
    [poc] nLocale=1100000000 nText=1100000000 sum=2200000001 INT_MAX=2147483647
    [poc] prepare failed (rc=1): no such function: fts5_locale -- fts5_locale() not present/reachable, nothing to trigger
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=1  poc_ran=True  patched=False
  commit=2ec78c0e4bab  note=build cached
  command=cd /tmp && cp /work/sqlite3.c . && cp /work/sqlite3.h . && cp /poc/poc.c . && gcc -g -O1 -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer -DSQLITE_CORE -DSQLITE_ENABLE_FTS5 -DSQLITE_MAX_LENGTH=1200000000 -I. -o poc_bin poc.c sqlite3.c -ldl -lpthread -lm && ./poc_bin
  poc_sha256=12841988ff2b8a52a7136ee6e5156d2efbb70ad972e97b648d6ae5dc0e25da63
  source_integrity=True
  sanitizer:
    VERIFY_EXIT=1
    
    [poc] nLocale=1100000000 nText=1100000000 sum=2200000001 INT_MAX=2147483647
    sqlite3.c:253475:9: runtime error: signed integer overflow: 1100000000 + 1100000001 cannot be represented in type 'int'
        #0 0x5576e05fe1e5 in fts5LocaleFunc /tmp/sqlite3.c:253475
        #1 0x5576e0732c86 in sqlite3VdbeExec /tmp/sqlite3.c:101910
        #2 0x5576e0737f93 in sqlite3Step /tmp/sqlite3.c:91317
        #3 0x5576e0737f93 in sqlite3_step /tmp/sqlite3.c:91378
        #4 0x5576e04baea1 in main /tmp/poc.c:74
        #5 0x7ffa27926d8f in __libc_start_call_main ../sysdeps/nptl/libc_start_call_main.h:58
        #6 0x7ffa27926e3f in __libc_start_main_impl ../csu/libc-start.c:392
        #7 0x5576e04bab44 in _start (/tmp/poc_bin+0x420b44)
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=4f2144dac011  note=build cached
  command=cd /tmp && cp /work/sqlite3.c . && cp /work/sqlite3.h . && cp /poc/poc.c . && gcc -g -O1 -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer -DSQLITE_CORE -DSQLITE_ENABLE_FTS5 -DSQLITE_MAX_LENGTH=1200000000 -I. -o poc_bin poc.c sqlite3.c -ldl -lpthread -lm && ./poc_bin
  poc_sha256=12841988ff2b8a52a7136ee6e5156d2efbb70ad972e97b648d6ae5dc0e25da63
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    VERIFY_EXIT=0
    
    [poc] nLocale=1100000000 nText=1100000000 sum=2200000001 INT_MAX=2147483647
    [poc] step rc=7: out of memory
    [poc] completed without crash
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
