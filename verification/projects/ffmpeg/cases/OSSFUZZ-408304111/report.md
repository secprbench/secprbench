# Verification report: pr_review_OSSFUZZ-408304111

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: IntegerOverflow
- **Intro commit**: `095f8038fa9180842cd38d4d61c7c47a02aad9ed`
- **Intro parent**: `6b31e42c47c00817f6249f43391873a15b1c00a4`
- **Fix commit**: `23592f942db93776dab65a5e92400bb2f037390e`
- **Affected files**: ['libswscale/output.c']

## PoC
- source: agent-generated (initial source: incomplete)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/ffmpeg/17e5df9c5df9f3442171/attempts/03/pocs/ffmpeg/OSSFUZZ-408304111`
- input: `None` (0 bytes)
- run.sh: True

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- Root cause per meta.json: commit 095f8038fa91 rewrote the bilinear vertical chroma interpolation in yuv2rgba64_full_1_c_template() (libswscale/output.c) from a simple sum (`ubuf0[i]+ubuf1[i]`) to a true weighted average (`ubuf0[i]*uvalpha1+ubuf1[i]*uvalpha`) but left U/V declared as plain `int` (fixed only later by 23592f942db9, which changes them to the project's overflow-tolerant `SUINT`). I confirmed this structurally: pre_intro's else-branch (uvalpha>=2048) always does a flat 50/50 sum of the two adjacent chroma rows regardless of the actual weight, while post_intro's else-branch (uvalpha>0) does a true proportional weighted sum that can put nearly 100% of the weight on one row. By placing an all-zero chroma row so it is structurally guaranteed to only ever be the second ("ubuf1") operand of a vertical pair (last source row, so it can never be picked as the lone/solo row used when uvalpha<2048), and by using sws_setColorspaceDetails (a legitimate public libswscale API, not a source edit) to raise c->yuv2rgb_u2b_coeff via saturation, I found a saturation value where the new weighted formula's more concentrated U value overflows 32-bit int arithmetic while the old formula's always-diluted 50/50 average does not. The same PoC and command were rebuilt/run unmodified against pre_intro, post_intro and post_benign (all with the same added -fsanitize=undefined instrumentation on output.c, since the project's default build only carries ASan which does not catch this UB): only post_intro crashes, both pre_intro and post_benign complete cleanly, and post_intro's crash backtrace lands exactly in the introduced weighted-average branch of yuv2rgba64_full_1_c_template, called via packed_vscale/ff_swscale/sws_scale exactly matching the original OSS-Fuzz crash state. This confirms the intro commit introduces the overflow and the paired fix commit (applied on top of intro, i.e. post_benign) removes it.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=6b31e42c47c0  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=ba6e8793fc5db767febcff658848f377c79de560c8cc7a004a35437740dd3278
  source_integrity=True
  output_tail:
    c:1829:45: note: place parentheses around the '+' expression to silence this warning
                    A2 = abuf0[i * 2 + 1] * 255 + 16384 >> 15;
                                                ^
                         (                             )
    libswscale/output.c:1938:12: warning: 233 enumeration values not handled in switch: 'AV_PIX_FMT_NONE', 'AV_PIX_FMT_YUV420P', 'AV_PIX_FMT_YUYV422'... [-Wswitch]
        switch(target) {
               ^~~~~~
    libswscale/output.c:3227:17: warning: 201 enumeration values not handled in switch: 'AV_PIX_FMT_NONE', 'AV_PIX_FMT_YUV420P', 'AV_PIX_FMT_YUYV422'... [-Wswitch]
            switch (dstFormat) {
                    ^~~~~~~~~
    libswscale/output.c:3460:17: warning: 209 enumeration values not handled in switch: 'AV_PIX_FMT_NONE', 'AV_PIX_FMT_YUV420P', 'AV_PIX_FMT_YUYV422'... [-Wswitch]
            switch (dstFormat) {
                    ^~~~~~~~~
    libswscale/output.c:3645:13: warning: 221 enumeration values not handled in switch: 'AV_PIX_FMT_NONE', 'AV_PIX_FMT_YUV420P', 'AV_PIX_FMT_RGB24'... [-Wswitch]
        switch (dstFormat) {
                ^~~~~~~~~
    8 warnings generated.
    setColorspaceDetails ret=0 sat_mult=9.000000 con_mult=1.000000
    scaling 32x32 -> 32x32
    done, no crash
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=1  poc_ran=True  patched=False
  commit=095f8038fa91  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=ba6e8793fc5db767febcff658848f377c79de560c8cc7a004a35437740dd3278
  source_integrity=True
  sanitizer:
    '... [-Wswitch]
        switch (dstFormat) {
                ^~~~~~~~~
    8 warnings generated.
    setColorspaceDetails ret=0 sat_mult=9.000000 con_mult=1.000000
    scaling 32x32 -> 32x32
    libswscale/output.c:1488:42: runtime error: signed integer overflow: 1610612736 + 1419706368 cannot be represented in type 'int'
        #0 0x55ad13f14c13 in yuv2rgba64_full_1_c_template /work/libswscale/output.c:1488:42
        #1 0x55ad13f14c13 in yuv2bgrx64be_full_1_c /work/libswscale/output.c:1581:1
        #2 0x55ad13e41f17 in packed_vscale /work/libswscale/vscale.c
        #3 0x55ad13e2e8d7 in ff_swscale /work/libswscale/swscale.c:531:13
        #4 0x55ad13e33851 in scale_internal /work/libswscale/swscale.c:1157:15
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=6b31e42c47c0  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=ba6e8793fc5db767febcff658848f377c79de560c8cc7a004a35437740dd3278
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    c:1835:45: note: place parentheses around the '+' expression to silence this warning
                    A2 = abuf0[i * 2 + 1] * 255 + 16384 >> 15;
                                                ^
                         (                             )
    libswscale/output.c:1947:12: warning: 233 enumeration values not handled in switch: 'AV_PIX_FMT_NONE', 'AV_PIX_FMT_YUV420P', 'AV_PIX_FMT_YUYV422'... [-Wswitch]
        switch(target) {
               ^~~~~~
    libswscale/output.c:3239:17: warning: 201 enumeration values not handled in switch: 'AV_PIX_FMT_NONE', 'AV_PIX_FMT_YUV420P', 'AV_PIX_FMT_YUYV422'... [-Wswitch]
            switch (dstFormat) {
                    ^~~~~~~~~
    libswscale/output.c:3472:17: warning: 209 enumeration values not handled in switch: 'AV_PIX_FMT_NONE', 'AV_PIX_FMT_YUV420P', 'AV_PIX_FMT_YUYV422'... [-Wswitch]
            switch (dstFormat) {
                    ^~~~~~~~~
    libswscale/output.c:3657:13: warning: 221 enumeration values not handled in switch: 'AV_PIX_FMT_NONE', 'AV_PIX_FMT_YUV420P', 'AV_PIX_FMT_RGB24'... [-Wswitch]
        switch (dstFormat) {
                ^~~~~~~~~
    8 warnings generated.
    setColorspaceDetails ret=0 sat_mult=9.000000 con_mult=1.000000
    scaling 32x32 -> 32x32
    done, no crash
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
