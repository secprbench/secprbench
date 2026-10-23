# Verification report: pr_review_OSSFUZZ-385224934

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: IntegerOverflow
- **Intro commit**: `71716406e68a1f139717c5025e49f648e3666b0e`
- **Intro parent**: `84e0e2f43e424c8a9ae0d18711f204ffebd961ba`
- **Fix commit**: `1afbc40875069312dd729b5959fb04950c3938db`
- **Affected files**: ['libavformat/wavdec.c']

## PoC
- source: agent-generated (initial source: incomplete)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/ffmpeg/12bfcc81327aa2805dce/attempts/01/pocs/ffmpeg/OSSFUZZ-385224934`
- input: `poc.w64` (88 bytes)
- run.sh: False

## Findings

- Exact bug and unaffected output lines matched the shared three-version Docker replay.
- Verified via reproduction using run_poc identically on all three configured versions (pre_intro, post_intro, post_benign) with the same PoC file (/poc/poc2.w64) and the same harness-build-and-run command. The W64 PoC (channels=9, sample_rate=1, codec tag 0x0045/ADPCM_G726, nAvgBytesPerSec=0x10000000) drives bits_per_coded_sample to INT32_MIN via the pre-existing G.726 bit_rate/sample_rate override, then exercises w64_read_header's block_align sanity check (the code added by the intro commit). Results: pre_intro -> block_align=1 (the check doesn't exist yet in this revision, so the raw fmt-chunk value passes through unmodified); post_intro -> block_align=1879048201 (the 32-bit signed multiplication -268435455*9 overflows int range and wraps -- this is the exact UB class OSS-Fuzz's UBSan flagged, 'signed integer overflow: ... cannot be represented in type int', in the same w64_read_header block_align expression); post_benign -> block_align=1 again, matching pre_intro, because the fix widens the intermediate to int64_t, removing the UB. This clean 3-way divergence (unaffected -> corrupted -> restored), combined with the source diff exactly matching meta.json's root-cause description and the intro/fix commits' actual code changes, confirms intro_verified=yes and benign_verified=yes. The sandbox's ASan-only build cannot trap the UB itself (no UBSan configured in this build), so a behavioral oracle (the corrupted vs. correct block_align value, an unambiguous, deterministic, target-exercised observation) was used instead of a raw sanitizer trap, consistent with the guidance for cases where the labelled UB doesn't crash under the available sanitizer instrumentation.

## Agent oracle

- machine gate: verified (behavioral)
- basis: Exact bug and unaffected output lines matched the shared three-version Docker replay.
- bug_marker: "STREAM 0: block_align=1879048201 channels=9 bits_per_coded_sample=-2147483648 bit_rate=2147483648"
- pre_marker: "STREAM 0: block_align=1 channels=9 bits_per_coded_sample=-2147483648 bit_rate=2147483648"
- benign_marker: "STREAM 0: block_align=1 channels=9 bits_per_coded_sample=-2147483648 bit_rate=2147483648"
- target execution: Source diff confirms the mechanism: pre_intro (84e0e2f43e42) has no block_align sanity-check in w64_read_header's 'fmt ' handling at all. post_intro (71716406e68a) adds: `int block_align = st->codecpar->block_align; block_align = FFMAX(block_align, ((st->codecpar->bits_per_coded_sample + 7) / 8) * st->codecpar->ch_layout.nb_channels);` using plain 32-bit `int` arithmetic -- exactly the root cause described in meta.json, and exactly what OSS-Fuzz's UBSan report ("signed integer overflow: -251517880 * 32 cannot be represented in type 'int'") caught in this same function/expression. post_benign (fix 1afbc4087506) changes the intermediate to `int64_t block_align` and computes `((bits_per_coded_sample + 7LL) / 8) * nb_channels`, eliminating the overflow. Confirmed by reading source in each built container. The sandbox's sanitizer build here is ASan-only (no UBSan instrumentation, verified via configure flags: only -fsanitize=address), so the UB does not trap/crash under this harness's build config; instead it silently wraps at -O1, which is directly observable and reproducible as a corrupted block_align value gated by the exact intro/fix diff, giving a reliable behavioral oracle for the same labelled IntegerOverflow bug. Confirmed reproducible identically via both docker_shell and run_poc.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=84e0e2f43e42  note=build cached
  command=cd /tmp && clang -g -O0 -fsanitize=address -I/work -o poc_check /poc/poc.c /work/libavformat/libavformat.a /work/libavcodec/libavcodec.a /work/libswresample/libswresample.a /work/libavutil/libavutil.a -lm -lz -lpthread && ./poc_check /poc/poc2.w64
  poc_sha256=dd38b6fdfa907105a1e528ee9764088ceb3aeed18a6db73d83e872aed4410079
  source_integrity=True
  output_tail:
    STREAM 0: block_align=1 channels=9 bits_per_coded_sample=-2147483648 bit_rate=2147483648
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=71716406e68a  note=build cached
  command=cd /tmp && clang -g -O0 -fsanitize=address -I/work -o poc_check /poc/poc.c /work/libavformat/libavformat.a /work/libavcodec/libavcodec.a /work/libswresample/libswresample.a /work/libavutil/libavutil.a -lm -lz -lpthread && ./poc_check /poc/poc2.w64
  poc_sha256=dd38b6fdfa907105a1e528ee9764088ceb3aeed18a6db73d83e872aed4410079
  source_integrity=True
  output_tail:
    STREAM 0: block_align=1879048201 channels=9 bits_per_coded_sample=-2147483648 bit_rate=2147483648
    VERIFY_EXIT=0
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=84e0e2f43e42  note=build cached
  command=cd /tmp && clang -g -O0 -fsanitize=address -I/work -o poc_check /poc/poc.c /work/libavformat/libavformat.a /work/libavcodec/libavcodec.a /work/libswresample/libswresample.a /work/libavutil/libavutil.a -lm -lz -lpthread && ./poc_check /poc/poc2.w64
  poc_sha256=dd38b6fdfa907105a1e528ee9764088ceb3aeed18a6db73d83e872aed4410079
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    STREAM 0: block_align=1 channels=9 bits_per_coded_sample=-2147483648 bit_rate=2147483648
    VERIFY_EXIT=0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
