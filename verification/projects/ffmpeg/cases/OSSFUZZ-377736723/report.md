# Verification report: pr_review_OSSFUZZ-377736723

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: IntegerOverflow
- **Intro commit**: `9cfc7a244052dced520776ff0ecc6f0a9390f62b`
- **Intro parent**: `6b7e4de0dbc78a630bfea27e917798b4d5b61abf`
- **Fix commit**: `02958ab7156b4e14f1918f2b72c6d3678852698f`
- **Affected files**: ['libavformat/mov.c']

## PoC
- source: agent-generated (initial source: incomplete)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/ffmpeg/198b67856ad28f7d1f8b/attempts/02/pocs/ffmpeg/OSSFUZZ-377736723`
- input: `None` (0 bytes)
- run.sh: True

## Findings

- Exact bug and unaffected output lines matched the shared three-version Docker replay.
- Root cause confirmed by direct code diff: mov_read_stts() in libavformat/mov.c (added by intro commit 9cfc7a244052, absent in parent 6b7e4de0dbc7) accumulates current_dts/corrected_dts (int64_t) from file-controlled 32-bit stts fields and computes `int64_t drift = (current_dts - corrected_dts)/FFMAX(sample_count,1);` via a plain signed subtraction. The fix commit 02958ab7156b changes only this one line to `av_sat_sub64(current_dts, corrected_dts)`, leaving the surrounding accumulation (`corrected_dts += ...`, `current_dts += ...`) untouched in both intro and benign builds -- matching the oss-fuzz report 'signed integer overflow: 7803923888585309955 - -3407677434275325337 cannot be represented in type int64_t'.
Because this verification build is ASan-only (confirmed via `./configure --extra-cflags='-fsanitize=address ...'`, no -fsanitize=undefined, and no sanitizer abort observed when the overflow fires), the UB manifests as silent value corruption rather than a trap. I used a behavioral oracle instead: a tiny harness (poc.c) linked against each version's built libavformat/libavcodec/libavutil calls avformat_open_input() on the crafted file and prints AVStream.duration.
Exact same target invocation used for all three versions: `bash /poc/run.sh >/dev/null 2>&1 && clang -g -O1 -fsanitize=address -fno-omit-frame-pointer -I/work -o /tmp/poc /poc/poc.c /work/libavformat/libavformat.a /work/libavcodec/libavcodec.a /work/libavutil/libavutil.a /work/libswresample/libswresample.a -lm -lz -lpthread -fsanitize=address && /tmp/poc /tmp/poc.mov`. run.sh deterministically builds /tmp/poc.mov from fixed embedded header/tail bytes plus a programmatically-built stts table of 4474 entries (4473 entries of sample_count=0xFFFFFFFF/sample_duration=0xFFF8AD00, then one tuning entry sample_count=0xEC9C7D99/sample_duration=0xFFF8AD00) chosen so current_dts-corrected_dts crosses INT64_MAX exactly on the last entry without either accumulator overflowing first.
Results (identical command, identical crafted input, all three revisions):
  pre_intro  (6b7e4de0dbc7, feature absent): STREAM 0 duration=10240 (=1.000000s, sane).
  post_intro (9cfc7a244052, buggy):          STREAM 0 duration=-9223372027293542051 (=-900719924540385.0s, garbage from the wrapped overflow).
  post_benign(fix applied, av_sat_sub64):    STREAM 0 duration=10240 (=1.000000s, sane again, matches pre_intro).
Reproduced consistently across repeated builds/runs (deterministic). This establishes the bug is introduced by 9cfc7a244052 (absent in parent), present in post_intro, and removed by the paired fix/benign commit -- confirming the labelled IntegerOverflow in mov_read_stts's drift calculation, surfaced here as corrupted output because this build's sanitizer configuration lacks UBSan.

## Agent oracle

- machine gate: verified (behavioral)
- basis: Exact bug and unaffected output lines matched the shared three-version Docker replay.
- bug_marker: "STREAM 0 duration=-9223372027293542051 time_base=1/10240 tb_num_duration_sec=-900719924540385.000000"
- pre_marker: "STREAM 0 duration=10240 time_base=1/10240 tb_num_duration_sec=1.000000"
- benign_marker: "STREAM 0 duration=10240 time_base=1/10240 tb_num_duration_sec=1.000000"
- target execution: Command (identical for all 3 versions): `bash /poc/run.sh >/dev/null 2>&1 && clang -g -O1 -fsanitize=address -fno-omit-frame-pointer -I/work -o /tmp/poc /poc/poc.c /work/libavformat/libavformat.a /work/libavcodec/libavcodec.a /work/libavutil/libavutil.a /work/libswresample/libswresample.a -lm -lz -lpthread -fsanitize=address && /tmp/poc /tmp/poc.mov`.
pre_intro  -> "STREAM 0 duration=10240 time_base=1/10240 tb_num_duration_sec=1.000000" / "FORMAT duration=1000000".
post_intro -> "STREAM 0 duration=-9223372027293542051 time_base=1/10240 tb_num_duration_sec=-900719924540385.000000" / "FORMAT duration=1000000" (only the per-stream duration, derived from mov_read_stts's drift/duration accumulation, is corrupted; container-level mvhd duration is untouched, pinpointing the corruption to mov_read_stts).
post_benign -> "STREAM 0 duration=10240 time_base=1/10240 tb_num_duration_sec=1.000000" (matches pre_intro).

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=6b7e4de0dbc7  note=build cached
  command=bash /poc/run.sh >/dev/null 2>&1 && clang -g -O1 -fsanitize=address -fno-omit-frame-pointer -I/work -o /tmp/poc /poc/poc.c /work/libavformat/libavformat.a /work/libavcodec/libavcodec.a /work/libavutil/libavutil.a /work/libswresample/libswresample.a -lm -lz -lpthread -fsanitize=address && /tmp/poc /tmp/poc.mov
  poc_sha256=56e8ad15389747d03cef20db78fb837158ccd4ee6e6629bc3304831d3597591a
  source_integrity=True
  output_tail:
    STREAM 0 duration=10240 time_base=1/10240 tb_num_duration_sec=1.000000
    FORMAT duration=1000000
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=9cfc7a244052  note=build cached
  command=bash /poc/run.sh >/dev/null 2>&1 && clang -g -O1 -fsanitize=address -fno-omit-frame-pointer -I/work -o /tmp/poc /poc/poc.c /work/libavformat/libavformat.a /work/libavcodec/libavcodec.a /work/libavutil/libavutil.a /work/libswresample/libswresample.a -lm -lz -lpthread -fsanitize=address && /tmp/poc /tmp/poc.mov
  poc_sha256=56e8ad15389747d03cef20db78fb837158ccd4ee6e6629bc3304831d3597591a
  source_integrity=True
  output_tail:
    STREAM 0 duration=-9223372027293542051 time_base=1/10240 tb_num_duration_sec=-900719924540385.000000
    FORMAT duration=1000000
    VERIFY_EXIT=0
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=6b7e4de0dbc7  note=build cached
  command=bash /poc/run.sh >/dev/null 2>&1 && clang -g -O1 -fsanitize=address -fno-omit-frame-pointer -I/work -o /tmp/poc /poc/poc.c /work/libavformat/libavformat.a /work/libavcodec/libavcodec.a /work/libavutil/libavutil.a /work/libswresample/libswresample.a -lm -lz -lpthread -fsanitize=address && /tmp/poc /tmp/poc.mov
  poc_sha256=56e8ad15389747d03cef20db78fb837158ccd4ee6e6629bc3304831d3597591a
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    STREAM 0 duration=10240 time_base=1/10240 tb_num_duration_sec=1.000000
    FORMAT duration=1000000
    VERIFY_EXIT=0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
