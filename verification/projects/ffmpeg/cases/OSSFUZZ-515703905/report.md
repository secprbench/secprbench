# Verification report: pr_review_OSSFUZZ-515703905

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: IntegerOverflow
- **Intro commit**: `baad75cafa6bac298b72c177f657a2eb8e31cff1`
- **Intro parent**: `86977fdb6bb0ba553a9c654309eb9c028a3777b4`
- **Fix commit**: `69c9f1158c153b2dc260aa724e5dc285286079b2`
- **Affected files**: ['libavcodec/aac/aacdec_usac.c']

## PoC
- source: agent-generated (initial source: incomplete)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/ffmpeg/d470df5e89c447add78d/attempts/05/pocs/ffmpeg/OSSFUZZ-515703905`
- input: `None` (0 bytes)
- run.sh: True

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- Root cause (meta.json): decode_tsd() in libavcodec/aac/aacdec_usac.c computes a binomial coefficient via `c *= k - p + h; c /= h;`; the intermediate product before the division by h can transiently exceed int64_t range when the USAC bitstream supplies large nb_slots/nb_tr_slots (reachable via MPS212's coreSbrFrameLengthIndex==4 and a large tsd_num_tr_slots), even though the final coefficient value fits in int64_t.

No existing PoC or usable seed was available (evidence/ empty, no run.sh provided). Hand-crafting a full raw USAC AudioSpecificConfig + frame bitstream that walks through loudness_set parsing, the USAC element loop, SBR data, spectral/TNS decoding, stereo_config_index selection, and the MPS212 CLD/ICC/IPD/SMG sections before reaching tsd_enable/tsd_num_tr_slots is prohibitively complex to derive purely from source reading for this pass. Instead I built a harness (/poc/poc.c + /poc/run.sh, both under /poc, no tracked target source modified) that compiles the real, unmodified aacdec_usac.c translation unit for each version and calls the actual decode_tsd() function directly with the exact (nb_tr_slots, nb_slots) values the bitstream parser would legally supply in the maximal overflow-triggering case identified in the root cause. Because decode_tsd doesn't exist pre-intro, run.sh detects this structurally (grep on the target's own source, not a hardcoded per-version branch) and poc.c substitutes a harmless stub, so the exact same PoC files run cleanly (exit 0) rather than failing to build.

Results via run_poc, identical driver/parameters/input across every version: post_intro reliably aborts with a UBSan signed-integer-overflow report pinpointing exactly line 1376 (`c *= k - p + h;`), matching the root cause precisely. post_benign (intro + official fix commit, which rewrites the loop with a `c <= s` bound and `c += c*(k-p)/h`) runs the identical harness/parameters cleanly with no overflow. pre_intro runs the identical harness/parameters cleanly too, but via the auto-selected stub path because the vulnerable function (and the whole USAC MPS212 temporal-shape-decoding feature) does not exist there at all — confirmed independently by a zero-match grep — meaning the bug was introduced wholesale together with new code, not a pre-existing flaw merely exposed later. This is a clean, sanitizer-confirmed regression bracketed exactly by intro/benign: intro_verified=yes, benign_verified=yes.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=86977fdb6bb0  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=fa601a271268a2b13b1e586ba151a2da5b27ba36b3e8a34f85c044aec444c0a6
  source_integrity=True
  output_tail:
    done (stub, feature absent), tsd_pos[0]=0
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=baad75cafa6b  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=fa601a271268a2b13b1e586ba151a2da5b27ba36b3e8a34f85c044aec444c0a6
  source_integrity=True
  sanitizer:
    _usac.c:296:17: warning: enumeration value 'ID_USAC_EXT' not handled in switch [-Wswitch]
            switch (e->type) {
                    ^~~~~~~
    1 warning generated.
    libavcodec/aac/aacdec_usac.c:1376:15: runtime error: signed integer overflow: 232714176627630544 * 62 cannot be represented in type 'long'
        #0 0x559222e4cf3a in decode_tsd_test /work/./libavcodec/aac/aacdec_usac.c:1376:15
        #1 0x559222e4c5d1 in main /poc/poc.c:86:5
        #2 0x7f3980e37d8f in __libc_start_call_main csu/../sysdeps/nptl/libc_start_call_main.h:58:16
        #3 0x7f3980e37e3f in __libc_start_main csu/../csu/libc-start.c:392:3
        #4 0x559222d79384 in _start (/tmp/poc_bin+0x470384) (BuildId: c911888f6b4ae016653552782694ac64fac00253)
    
    SUMMARY: UndefinedBehaviorSanitizer: undefined-behavior libavcodec/aac/aacdec_usac.c:1376:15 in
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=86977fdb6bb0  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=fa601a271268a2b13b1e586ba151a2da5b27ba36b3e8a34f85c044aec444c0a6
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    done, tsd_pos[0]=1
    VERIFY_EXIT=0
    
    In file included from /poc/poc.c:60:
    ./libavcodec/aac/aacdec_usac.c:296:17: warning: enumeration value 'ID_USAC_EXT' not handled in switch [-Wswitch]
            switch (e->type) {
                    ^~~~~~~
    1 warning generated.
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
