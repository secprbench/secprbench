# Verification report: pr_review_OSSFUZZ-471569982

- **Status**: `inconclusive`
- **Intro verified**: None
- **Benign verified**: None
- **Bug type**: LogicError
- **Intro commit**: `589b3ed943d46ba163cea383634d67319af11cba`
- **Intro parent**: `5674879db5ea411b42e55c3906fa586f540bf637`
- **Fix commit**: `be1fd6d9d4b1e6371c1e0852168d728aaecb71b2`
- **Affected files**: ['libavcodec/prores_raw.c']

## PoC
- source: agent-generated (initial source: incomplete)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/ffmpeg/ee81b0b8c341cf989f28/attempts/01/pocs/ffmpeg/OSSFUZZ-471569982`
- input: `input.bin` (250 bytes)
- run.sh: False

## Findings

- The agent claim lacks a matching admissible three-version oracle.
- post_intro (589b3ed943d4, the commit that adds the entire ProRes RAW decoder including prores_raw.c) crashes deterministically with exactly the reported defect: `libavcodec/prores_raw.c:143:31: runtime error: shift exponent -1 is negative` at `const int block_mask = (1 << log2_nb_blocks) - 1;` inside decode_comp(), reached via decode_tile -> decode_tiles -> avcodec_default_execute2 -> decode_frame — matching the OSS-Fuzz reported crash stack (decode_comp/decode_tiles/avcodec_default_execute2) and crash type (Undefined-shift) exactly. pre_intro (5674879db5ea) has no prores_raw.c at all (only prores_raw_parser.c exists there; AV_CODEC_ID_PRORES_RAW is a declared enum value but no decoder is registered), so avcodec_find_decoder() returns NULL and the harness exits cleanly printing 'no decoder' — the flaw cannot manifest because the feature containing it doesn't exist yet, confirming the bug was introduced exactly at 589b3ed943d4. post_benign, rebuilt the same way and run on the identical input, completes cleanly (exit=0, no sanitizer report); avcodec_send_packet instead returns an AVERROR (invalid data), because that source now contains the validation `if (avctx->width - tile->x < 16) return AVERROR_INVALIDDATA;` added to the per-tile offset-parsing loop (confirmed present in post_benign and absent in post_intro by direct grep), matching exactly what the real fix commit be1fd6d9d4b1 ("Tiles of width less than 16 result in undefined behavior") does. All three runs used the identical crafted input.bin via run_poc, isolating the observed sanitizer/behavior difference to the labelled code change.

## Agent oracle

- machine gate: inconclusive (unproven)
- basis: The agent claim lacks a matching admissible three-version oracle.
- bug_marker: "libavcodec/prores_raw.c:143:31: runtime error: shift exponent -1 is negative ... SUMMARY: UndefinedBehaviorSanitizer: undefined-behavior libavcodec/prores_raw.c:143:31"
- pre_marker: "no decoder (AV_CODEC_ID_PRORES_RAW enum exists but no decoder registered; feature not yet introduced)"
- benign_marker: "send_packet ret=-1163346256 (AVERROR_INVALIDDATA); DONE \u2014 exit=0, no sanitizer report, clean rejection via the new `avctx->width - tile->x < 16` check"
- target execution: post_intro stack via run_poc: #0 decode_comp libavcodec/prores_raw.c:143:31, #1 decode_tile prores_raw.c:278, #2 decode_tiles prores_raw.c:311, #3 avcodec_default_execute2, #4 decode_frame prores_raw.c:482 — matches OSS-Fuzz reported Crash State (decode_comp/decode_tiles/avcodec_default_execute2) and Crash Type Undefined-shift. Source grep confirms `if (avctx->width - tile->x < 16) return AVERROR_INVALIDDATA;` is present in post_benign and absent in post_intro, matching fix commit be1fd6d9d4b1's stated purpose.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=1  poc_ran=True  patched=False
  commit=5674879db5ea  note=build cached
  command=bash -c '
set -e
cd /work
if [ -f libavcodec/prores_raw.c ]; then
  clang -I. -I./ -D_ISOC11_SOURCE -D_FILE_OFFSET_BITS=64 -D_LARGEFILE_SOURCE -D_POSIX_C_SOURCE=200112 -D_XOPEN_SOURCE=600 -DPIC -I./compat/stdbit -DZLIB_CONST -DHAVE_AV_CONFIG_H -DBUILDING_avcodec -g -O1 -fsanitize=address,undefined -fno-omit-frame-pointer -std=c17 -fPIC -pthread -g -Wno-parentheses -fno-math-errno -fno-signed-zeros -mstack-alignment=16 -Qunused-arguments -c -o /tmp/prores_raw_ubsan.o libavcodec/prores_raw.c
  cp /work/libavcodec/libavcodec.a /tmp/libavcodec_test.a
  ar d /tmp/libavcodec_test.a prores_raw.o
  EXTRA_OBJ=/tmp/prores_raw_ubsan.o
  ARC=/tmp/libavcodec_test.a
else
  EXTRA_OBJ=
  ARC=/work/libavcodec/libavcodec.a
fi
cp /poc/poc.c /tmp/poc.c
clang -g -O1 -fsanitize=address,undefined -fno-omit-frame-pointer -I/work -DHAVE_AV_CONFIG_H -o /tmp/poc /tmp/poc.c $EXTRA_OBJ $ARC /work/libavformat/libavformat.a /work/libavutil/libavutil.a /work/libswresample/libswresample.a -lm -lpthread -lz
/tmp/poc /poc/input.bin
echo RUN_EXIT=$?
'
  poc_sha256=f2b8ec485fd46dda85760332b53da203a9d8d7cbd9a1f06868e97e2b826c73be
  source_integrity=True
  output_tail:
    VERIFY_EXIT=1
    
    no decoder
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=589b3ed943d4  note=build cached
  command=bash -c '
set -e
cd /work
if [ -f libavcodec/prores_raw.c ]; then
  clang -I. -I./ -D_ISOC11_SOURCE -D_FILE_OFFSET_BITS=64 -D_LARGEFILE_SOURCE -D_POSIX_C_SOURCE=200112 -D_XOPEN_SOURCE=600 -DPIC -I./compat/stdbit -DZLIB_CONST -DHAVE_AV_CONFIG_H -DBUILDING_avcodec -g -O1 -fsanitize=address,undefined -fno-omit-frame-pointer -std=c17 -fPIC -pthread -g -Wno-parentheses -fno-math-errno -fno-signed-zeros -mstack-alignment=16 -Qunused-arguments -c -o /tmp/prores_raw_ubsan.o libavcodec/prores_raw.c
  cp /work/libavcodec/libavcodec.a /tmp/libavcodec_test.a
  ar d /tmp/libavcodec_test.a prores_raw.o
  EXTRA_OBJ=/tmp/prores_raw_ubsan.o
  ARC=/tmp/libavcodec_test.a
else
  EXTRA_OBJ=
  ARC=/work/libavcodec/libavcodec.a
fi
cp /poc/poc.c /tmp/poc.c
clang -g -O1 -fsanitize=address,undefined -fno-omit-frame-pointer -I/work -DHAVE_AV_CONFIG_H -o /tmp/poc /tmp/poc.c $EXTRA_OBJ $ARC /work/libavformat/libavformat.a /work/libavutil/libavutil.a /work/libswresample/libswresample.a -lm -lpthread -lz
/tmp/poc /poc/input.bin
echo RUN_EXIT=$?
'
  poc_sha256=f2b8ec485fd46dda85760332b53da203a9d8d7cbd9a1f06868e97e2b826c73be
  source_integrity=True
  sanitizer:
    VERIFY_EXIT=134
    
    [prores_raw @ 0x618000000080] picture resolution change: 0x0 -> 130x16
    libavcodec/prores_raw.c:143:31: runtime error: shift exponent -1 is negative
        #0 0x56527f8d50f7 in decode_comp /work/libavcodec/prores_raw.c:143:31
        #1 0x56527f8d240c in decode_tile /work/libavcodec/prores_raw.c:278:11
        #2 0x56527f8d240c in decode_tiles /work/libavcodec/prores_raw.c:311:12
        #3 0x56527f942c20 in avcodec_default_execute2 /work/libavcodec/avcodec.c:92:17
        #4 0x56527f8cfc3e in decode_frame /work/libavcodec/prores_raw.c:482:9
        #5 0x56527fb39a19 in decode_simple_internal /work/libavcodec/decode.c:439:16
        #6 0x56527fb39a19 in decode_simple_receive_frame /work/libavcodec/decode.c:597:15
        #7 0x56527fb39a19 in ff_decode_receive_frame_internal /work/libavcodec/decode.c:633:15
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=5674879db5ea  note=build cached
  command=bash -c '
set -e
cd /work
if [ -f libavcodec/prores_raw.c ]; then
  clang -I. -I./ -D_ISOC11_SOURCE -D_FILE_OFFSET_BITS=64 -D_LARGEFILE_SOURCE -D_POSIX_C_SOURCE=200112 -D_XOPEN_SOURCE=600 -DPIC -I./compat/stdbit -DZLIB_CONST -DHAVE_AV_CONFIG_H -DBUILDING_avcodec -g -O1 -fsanitize=address,undefined -fno-omit-frame-pointer -std=c17 -fPIC -pthread -g -Wno-parentheses -fno-math-errno -fno-signed-zeros -mstack-alignment=16 -Qunused-arguments -c -o /tmp/prores_raw_ubsan.o libavcodec/prores_raw.c
  cp /work/libavcodec/libavcodec.a /tmp/libavcodec_test.a
  ar d /tmp/libavcodec_test.a prores_raw.o
  EXTRA_OBJ=/tmp/prores_raw_ubsan.o
  ARC=/tmp/libavcodec_test.a
else
  EXTRA_OBJ=
  ARC=/work/libavcodec/libavcodec.a
fi
cp /poc/poc.c /tmp/poc.c
clang -g -O1 -fsanitize=address,undefined -fno-omit-frame-pointer -I/work -DHAVE_AV_CONFIG_H -o /tmp/poc /tmp/poc.c $EXTRA_OBJ $ARC /work/libavformat/libavformat.a /work/libavutil/libavutil.a /work/libswresample/libswresample.a -lm -lpthread -lz
/tmp/poc /poc/input.bin
echo RUN_EXIT=$?
'
  poc_sha256=f2b8ec485fd46dda85760332b53da203a9d8d7cbd9a1f06868e97e2b826c73be
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    RUN_EXIT=0
    VERIFY_EXIT=0
    
    [prores_raw @ 0x618000000080] picture resolution change: 0x0 -> 130x16
    send_packet ret=-1163346256
    DONE
```

## Interpretation

The available evidence does not establish both labels. Inspect the findings and per-version results for the limiting reason.
