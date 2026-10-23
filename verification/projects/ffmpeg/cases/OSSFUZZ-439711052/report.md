# Verification report: pr_review_OSSFUZZ-439711052

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: IntegerOverflow
- **Intro commit**: `efa9d3deca30b47616721f60d8e79b1ccdaaefbc`
- **Intro parent**: `299d9115d4c7c6c108197f48960e140d7433dae6`
- **Fix commit**: `d448d6d1a0a4cdc76499c137742fdd8b30b9e7de`
- **Affected files**: ['libavcodec/hevc/sei.c', 'libavcodec/hevc/sei.h']

## PoC
- source: agent-generated (initial source: incomplete)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/ffmpeg/150e39ef7278cdc764c3/attempts/07/pocs/ffmpeg/OSSFUZZ-439711052`
- input: `sei_msg.bin` (40 bytes)
- run.sh: False

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- Root cause matches meta.json exactly: in decode_nal_sei_3d_reference_displays_info() (added by intro commit efa9d3deca30), the Exp-Golomb-decoded num_ref_displays is stored into a uint8_t struct field before the ">31" bound check runs, so a raw value like 287 truncates to 31, passes the check, becomes 32 after +1, and the subsequent loop performs an out-of-bounds write to left_view_id[31] (array size 31). Proven by recompiling only the unmodified sei.c with UBSan(+ASan,+bounds) instrumentation (matching the original OSS-Fuzz job's sanitizer, absent from this task's default ASan-only build) and running the identical 40-byte crafted SEI payload through run_poc with a minimal harness calling the real target function ff_hevc_decode_nal_sei, cross-checked via the full ffmpeg HEVC decoder pipeline. post_intro reproducibly hits 'index 31 out of bounds for type uint16_t[31]' at sei.c:171 on every run; pre_intro (parent commit, feature not yet present) and post_benign (fix commit applied) both complete cleanly on the exact same bytes/command via run_poc — pre_intro because the SEI payload type isn't handled yet, post_benign because the fix's `unsigned num_ref_displays` local-variable check now correctly rejects the raw value 287 with AVERROR_INVALIDDATA before any truncation/array access occurs. Same input, same command, same harness across all three revisions — only the target revision differs.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.
- bug_marker: "libavcodec/hevc/sei.c:171:9: runtime error: index 31 out of bounds for type 'uint16_t[31]' (aka 'unsigned short[31]')"
- pre_marker: "ff_hevc_decode_nal_sei returned 1 (payload type 176 not yet implemented in pre_intro; message treated as unhandled and skipped cleanly, exit=0, no crash)"
- benign_marker: "ff_hevc_decode_nal_sei returned -1094995529 (AVERROR_INVALIDDATA), exit=0, no crash: the fix computes the golomb value into a local `unsigned num_ref_displays` and checks `> 31` (287 > 31 is true) before truncating/storing it into the uint8_t struct field, so the same input is cleanly rejected instead of causing an OOB access."
- target execution: run_poc(post_intro, same 40-byte input/command): crashed=True, "libavcodec/hevc/sei.c:171:9: runtime error: index 31 out of bounds for type 'uint16_t[31]'" in decode_nal_sei_3d_reference_displays_info -> decode_nal_sei_prefix -> decode_nal_sei_message -> ff_hevc_decode_nal_sei. This is exactly the off-by-one OOB write into HEVCSEITDRDI.left_view_id[31] caused by storing the raw get_ue_golomb() value (287) into the uint8_t field num_ref_displays before the ">31" bound check, so the truncated value (287 mod 256 = 31) passes validation, is incremented to 32, and the loop runs i=0..31 (32 iterations) against a 31-element array.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=299d9115d4c7  note=build cached
  command=UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 ASAN_OPTIONS=halt_on_error=1 /work/poc_bin $INPUT
  poc_sha256=d813511e96e852a6cbdc5c5c4721fe6bf85fac1feef89c78a14e44261eabd90e
  source_integrity=True
  output_tail:
    VERIFY_EXIT=0
    
    read 40 bytes
    ff_hevc_decode_nal_sei returned 1
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=1  poc_ran=True  patched=False
  commit=efa9d3deca30  note=build cached
  command=UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 ASAN_OPTIONS=halt_on_error=1 /work/poc_bin $INPUT
  poc_sha256=d813511e96e852a6cbdc5c5c4721fe6bf85fac1feef89c78a14e44261eabd90e
  source_integrity=True
  sanitizer:
    VERIFY_EXIT=1
    
    read 40 bytes
    libavcodec/hevc/sei.c:171:9: runtime error: index 31 out of bounds for type 'uint16_t[31]' (aka 'unsigned short[31]')
        #0 0x55ff6c3b6b9e in decode_nal_sei_3d_reference_displays_info /work/libavcodec/hevc/sei.c:171:28
        #1 0x55ff6c3b6b9e in decode_nal_sei_prefix /work/libavcodec/hevc/sei.c:220:16
        #2 0x55ff6c3b6b9e in decode_nal_sei_message /work/libavcodec/hevc/sei.c:274:16
        #3 0x55ff6c3b6b9e in ff_hevc_decode_nal_sei /work/libavcodec/hevc/sei.c:293:15
        #4 0x55ff6c3b41c4 in main /poc/poc.c:23:15
        #5 0x7f1eb809dd8f in __libc_start_call_main csu/../sysdeps/nptl/libc_start_call_main.h:58:16
        #6 0x7f1eb809de3f in __libc_start_main csu/../csu/libc-start.c:392:3
        #7 0x55ff6c2f6294 in _start (/work/poc_bin+0x439294) (BuildId: 9fc63073ad8f5b7697b620247fb5135851d434b1)
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=299d9115d4c7  note=build cached
  command=UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 ASAN_OPTIONS=halt_on_error=1 /work/poc_bin $INPUT
  poc_sha256=d813511e96e852a6cbdc5c5c4721fe6bf85fac1feef89c78a14e44261eabd90e
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    VERIFY_EXIT=0
    
    read 40 bytes
    ff_hevc_decode_nal_sei returned -1094995529
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
