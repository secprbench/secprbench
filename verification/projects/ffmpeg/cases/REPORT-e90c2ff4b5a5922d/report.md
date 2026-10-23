# Verification report: pr_review_REPORT-e90c2ff4b5a5922d

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: OutOfBoundsRead
- **Intro commit**: `fe1ffd63fb09fc8655487046f3ad2b372fef5497`
- **Intro parent**: `ec86dade2fc3bb7f9e718248045df066611426a6`
- **Fix commit**: `e90c2ff4b5a5922d2cad1acd41595084f71d74a8`
- **Affected files**: ['libavcodec/libdav1d.c']

## PoC
- source: agent-generated (initial source: no_poc)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/ffmpeg/cc39a746da6f61de7c3e/attempts/01/pocs/ffmpeg/REPORT-e90c2ff4b5a5922d`
- input: `harness_common.h` (1974 bytes)
- run.sh: True

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- Root cause confirmed by direct source diff across the three commits and by execution. pre_intro (ec86dade2fc3) unconditionally reads provider_code via the checked bytestream2_get_be16() for every country code -- safe (silently returns 0 on short input, no OOB). post_intro (fe1ffd63fb09) refactored the country_code dispatch into a switch statement and, only for the US branch, replaced this with the unchecked bytestream2_get_be16u() with no preceding length check -- an out-of-bounds read of up to 2 bytes whenever the ITU-T T.35 payload for country_code=US (0xB5) is shorter than 2 bytes, exactly as described by the reporter/fix commit message. post_benign (companion of fix e90c2ff4b5a5, built on the ec86dade2fc3 parent) adds `if (bytestream2_get_bytes_left(&gb) < 2) return AVERROR_INVALIDDATA;` immediately before that same unchecked read, closing the gap.

Because this ffmpeg build has CONFIG_LIBDAV1D=0 in all three built trees (confirmed via `#define CONFIG_LIBDAV1D 0` in config.h and `libdav1d='no'` in config.mak, and the total absence of any dav1d headers/library in the image), libavcodec/libdav1d.c is not compiled into the tested binary at all -- there is no `ffmpeg -c:v libdav1d` decode path reachable by any input, and dav1d/dav1d.h is unavailable to even compile the file standalone with its real API. No existing PoC/run.sh was provided (source: no_poc). I therefore built a harness (/poc/run.sh, harness_common.h, harness_main.h -- byte-identical across all three runs, containing only real/unmodified ffmpeg header includes, minimal struct typedefs matching the real dav1d API fields actually touched, and a fixed main() constructing the reporter's crafted Dav1dITUTT35 input) whose run.sh: (1) extracts, unmodified, only the body of parse_itut_t35_metadata() from THIS container's own /work/libavcodec/libdav1d.c (i.e. from the actual target source for whichever commit that container was built from -- the only thing that legitimately differs between runs); (2) compiles it together with the fixed harness against the real, unmodified /work headers (bytestream.h, itut35.h, hdr_dynamic_metadata.h, atsc_a53.h, dovi_rpu.h) and static libs (libavcodec.a, libavutil.a) built for that commit; (3) runs it against the same crafted struct. The command (`sh /poc/run.sh`) and every file under /poc are identical for all three invocations; only the per-commit target source that command reads from /work differs -- exactly analogous to how the same PoC input is normally run against each commit's differently built target binary.

Build note: the harness must be compiled at -O0. At -O1 (ffmpeg's own CFLAGS), LLVM -- given full visibility of this tiny, single-translation-unit program where both the malloc(1) and the resulting out-of-bounds read are visible/inlinable -- elides the faulting load (a known optimizer artifact exploiting "read past object end" UB when the allocation size is statically visible in the same program). That elision is impossible in the real target, where the allocation happens deep inside the separately-compiled dav1d library and the read happens in ffmpeg's own object file, with no visibility across that boundary; -O0 for this isolated harness avoids the artifact while still executing byte-for-byte the same target code path. This was independently confirmed by direct experiment: the identical unmodified post_intro function body compiled at -O1 completed without a sanitizer report, but crashed with the exact expected ASan trace at -O0; pre_intro and post_benign both complete cleanly at -O0 with the same harness/input.

Result: post_intro reliably reproduces a heap-buffer-overflow READ of size 2 via bytestream_get_be16 -> bytestream2_get_be16u -> parse_itut_t35_metadata, "0 bytes to the right of 1-byte region" (i.e. exactly the reported 2-bytes-read-from-a-1-byte-allocation overflow). pre_intro and post_benign, run via the identical run_poc command, complete cleanly with no sanitizer report. intro_verified=yes, benign_verified=yes.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=ec86dade2fc3  note=build cached
  command=sh /poc/run.sh
  poc_sha256=e56a6c41ce5f76b918ae0c0812eba5013a4f2122ba8dc07f9f88e67d5bb4cce1
  source_integrity=True
  output_tail:
    PARSE_RESULT=0
    DONE_NO_CRASH
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=1  poc_ran=True  patched=False
  commit=fe1ffd63fb09  note=build cached
  command=sh /poc/run.sh
  poc_sha256=e56a6c41ce5f76b918ae0c0812eba5013a4f2122ba8dc07f9f88e67d5bb4cce1
  source_integrity=True
  sanitizer:
    VERIFY_EXIT=1
    
    =================================================================
    ==16==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x602000000011 at pc 0x5600cb248df3 bp 0x7ffc896b9230 sp 0x7ffc896b9228
    READ of size 2 at 0x602000000011 thread T0
        #0 0x5600cb248df2 in bytestream_get_be16 /work/libavcodec/bytestream.h:98:1
        #1 0x5600cb248df2 in bytestream2_get_be16u /work/libavcodec/bytestream.h:98:1
        #2 0x5600cb248df2 in parse_itut_t35_metadata /tmp/tmp.fLVxmJFMBs/poc.c:68:25
        #3 0x5600cb2487ff in main /tmp/tmp.fLVxmJFMBs/poc.c:172:11
        #4 0x7f7649d0ad8f in __libc_start_call_main csu/../sysdeps/nptl/libc_start_call_main.h:58:16
        #5 0x7f7649d0ae3f in __libc_start_main csu/../csu/libc-start.c:392:3
        #6 0x5600cb18a7d4 in _start (/tmp/tmp.fLVxmJFMBs/poc+0x4607d4) (BuildId: 6b52c8aecd1dbadc73405bff875e372068fd4aad)
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=ec86dade2fc3  note=build cached
  command=sh /poc/run.sh
  poc_sha256=e56a6c41ce5f76b918ae0c0812eba5013a4f2122ba8dc07f9f88e67d5bb4cce1
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    PARSE_RESULT=-1094995529
    DONE_NO_CRASH
    VERIFY_EXIT=0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
