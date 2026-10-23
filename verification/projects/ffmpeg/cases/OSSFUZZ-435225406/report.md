# Verification report: pr_review_OSSFUZZ-435225406

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: IntegerOverflow
- **Intro commit**: `7c5319e6924fd82772eff890df191f973767d38e`
- **Intro parent**: `ce172bc362f09a12dc422283d81313bde4920f51`
- **Fix commit**: `75f30b4d3e2320275b60be1cf3213ce2cbf55ff8`
- **Affected files**: ['libavcodec/vvc/ctu.c']

## PoC
- source: agent-generated (initial source: incomplete)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/ffmpeg/047e8d10ad1044c1c66f/attempts/04/pocs/ffmpeg/OSSFUZZ-435225406`
- input: `None` (0 bytes)
- run.sh: True

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- Verified by direct code execution of the unmodified vulnerable function across all three revisions using the identical harness/input:
- pre_intro (ce172bc362f0): ff_vvc_palette_escape_val(lc) (old 1-arg API) decodes the same bits, and the caller checks `coeff >= (1U << bit_depth)` BEFORE the multiply, returning AVERROR_INVALIDDATA cleanly (no overflow). run_poc: exit=0, crashed=False, prints "palette_subblock_data returned -1094995529".
- post_intro (7c5319e6924f): ff_vvc_palette_escape_val(lc, max) (new failable API) returns the same negative sentinel, but the `if (coeff < 0) return ...` check was placed AFTER `const int pixel = av_clip_intp2(RSHIFT(coeff * scale, 6), ...)`, so coeff (-1094995529) * scale (64) executes and overflows signed int. run_poc: exit=134, crashed=True, UBSan report: "libavcodec/vvc/ctu.c:2057:53: runtime error: signed integer overflow: -1094995529 * 64 cannot be represented in type 'int'" inside palette_subblock_data — this exactly matches the upstream fix commit's cited UBSan finding ("-1094995529 * 6528") at the same source line/function, just with a different (still overflowing) scale value produced by our minimal QP setup.
- post_benign (fix applied on ce172bc362f0): the `if (coeff < 0) return AVERROR_INVALIDDATA;` check is moved BEFORE the multiply/pixel computation (matching the real fix), so the function returns before the multiply. run_poc: exit=0, crashed=False, same clean "-1094995529" return as pre_intro.

The same input bytes, the same harness call into the same static function, and the same build/run command (/poc/run.sh, invoked identically by run_poc) were used for all three revisions — only the target source under test differed. This isolates the regression to the check-after-multiply ordering introduced by 7c5319e6924f and confirms the companion patch removes it, exactly as described in root_cause/fix_message.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=ce172bc362f0  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=8b6df65cd42ec7e913fbdb6968e910be243dd9174d6d802ae350c3d9532ebf34
  source_integrity=True
  output_tail:
    palette_subblock_data returned -1094995529
    VERIFY_EXIT=0
    
    In file included from /poc/harness.c:13:
    /work/libavcodec/vvc/ctu.c:170:20: warning: passing 'int8_t *' (aka 'signed char *') to parameter of type 'uint8_t *' (aka 'unsigned char *') converts between pointers to integer types with different sign [-Wpointer-sign]
        set_cb_tab(lc, lc->fc->tab.qp[LUMA], ep->qp_y);
                       ^~~~~~~~~~~~~~~~~~~~
    /work/libavcodec/vvc/ctu.c:121:60: note: passing argument to parameter 'tab' here
    static void set_cb_tab(const VVCLocalContext *lc, uint8_t *tab, const uint8_t v)
                                                               ^
    /work/libavcodec/vvc/ctu.c:181:16: warning: passing 'int8_t *' (aka 'signed char *') to parameter of type 'uint8_t *' (aka 'unsigned char *') converts between pointers to integer types with different sign [-Wpointer-sign]
        set_tb_tab(lc->fc->tab.qp[tb->c_idx], lc->cu->qp[idx], lc->fc, tb);
                   ^~~~~~~~~~~~~~~~~~~~~~~~~
    /work/libavcodec/vvc/ctu.c:59:33: note: passing argument to parameter 'tab' here
    static void set_tb_tab(uint8_t *tab, uint8_t v, const VVCFrameContext *fc,
                                    ^
    2 warnings generated.
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=7c5319e6924f  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=8b6df65cd42ec7e913fbdb6968e910be243dd9174d6d802ae350c3d9532ebf34
  source_integrity=True
  sanitizer:
    argument to parameter 'tab' here
    static void set_tb_tab(uint8_t *tab, uint8_t v, const VVCFrameContext *fc,
                                    ^
    2 warnings generated.
    /work/libavcodec/vvc/ctu.c:2057:53: runtime error: signed integer overflow: -1094995529 * 64 cannot be represented in type 'int'
        #0 0x56133fdca3ec in palette_subblock_data /work/libavcodec/vvc/ctu.c:2057:53
        #1 0x56133fdc5057 in main /poc/harness.c:87:15
        #2 0x7f45d355dd8f in __libc_start_call_main csu/../sysdeps/nptl/libc_start_call_main.h:58:16
        #3 0x7f45d355de3f in __libc_start_main csu/../csu/libc-start.c:392:3
        #4 0x56133fcfb0e4 in _start (/tmp/poc_harness+0x4880e4) (BuildId: 26f7eb737d4b392c053cade07eaf89e2da1aefb7)
    
    SUMMARY: UndefinedBehaviorSanitizer: undefined-behavior /work/libavcodec/vvc/ctu.c:2057:53 in
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=ce172bc362f0  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=8b6df65cd42ec7e913fbdb6968e910be243dd9174d6d802ae350c3d9532ebf34
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    palette_subblock_data returned -1094995529
    VERIFY_EXIT=0
    
    In file included from /poc/harness.c:13:
    /work/libavcodec/vvc/ctu.c:171:20: warning: passing 'int8_t *' (aka 'signed char *') to parameter of type 'uint8_t *' (aka 'unsigned char *') converts between pointers to integer types with different sign [-Wpointer-sign]
        set_cb_tab(lc, lc->fc->tab.qp[LUMA], ep->qp_y);
                       ^~~~~~~~~~~~~~~~~~~~
    /work/libavcodec/vvc/ctu.c:122:60: note: passing argument to parameter 'tab' here
    static void set_cb_tab(const VVCLocalContext *lc, uint8_t *tab, const uint8_t v)
                                                               ^
    /work/libavcodec/vvc/ctu.c:182:16: warning: passing 'int8_t *' (aka 'signed char *') to parameter of type 'uint8_t *' (aka 'unsigned char *') converts between pointers to integer types with different sign [-Wpointer-sign]
        set_tb_tab(lc->fc->tab.qp[tb->c_idx], lc->cu->qp[idx], lc->fc, tb);
                   ^~~~~~~~~~~~~~~~~~~~~~~~~
    /work/libavcodec/vvc/ctu.c:60:33: note: passing argument to parameter 'tab' here
    static void set_tb_tab(uint8_t *tab, uint8_t v, const VVCFrameContext *fc,
                                    ^
    2 warnings generated.
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
