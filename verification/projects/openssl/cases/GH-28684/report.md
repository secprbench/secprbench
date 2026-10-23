# Verification report: pr_review_GH-28684

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: LogicError
- **Intro commit**: `03ce37e11729bbe9964bd613c0eed6156b920208`
- **Intro parent**: `7cbca5a6d6e792c75c414e1f3fb22e2afae67988`
- **Fix commit**: `22417bc14d6bde173425ba4f87c68be0cf394fa4`
- **Affected files**: ['crypto/chacha/chacha_riscv.c']

## PoC
- source: agent-generated (initial source: no_poc)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/openssl/c1c713783c74848e6cf4/attempts/01/pocs/openssl/GH-28684`
- input: `None` (0 bytes)
- run.sh: True

## Findings

- Exact bug and unaffected output lines matched the shared three-version Docker replay.
- The affected file (crypto/chacha/chacha_riscv.c) is only compiled/exercised on a riscv64 target; this Docker image builds/runs strictly linux-x86_64 (configdata.pm target=linux-x86_64-clang; the produced chacha object is chacha-x86_64.o) with no riscv64 cross-compiler or qemu-riscv64 available, and the reporter states the actual crash requires real riscv64-V hardware (QEMU does not reproduce it). So the literal hardware crash cannot be triggered here. Since this is a LogicError (a missing-condition dispatch defect, not a sanitizer-catchable memory fault), I instead built a precise, self-checking behavioral PoC: it compiles the exact, unmodified chacha_riscv.c source from each revision against a stub translation unit supplying the capability array, riscv_vlen(), and instrumented stand-ins for the low-level implementation functions, then invokes the real ChaCha20_ctr32() entry point with identical misaligned out/inp pointers on every version, via run_poc using the same /poc/run.sh command on pre_intro, post_intro, and post_benign. The observed dispatch decision diverges exactly as the report describes: post_intro routes misaligned buffers into the vector implementation (missing alignment gate = the introduced bug), post_benign routes the same misaligned buffers into the safe scalar C fallback (alignment gate restored = the fix), and pre_intro does not exhibit the same flaw because it lacks the vulnerable split entirely. This satisfies the same-command-across-versions invariant and yields an unambiguous verdict without requiring riscv64 hardware.

## Agent oracle

- machine gate: verified (behavioral)
- basis: Exact bug and unaffected output lines matched the shared three-version Docker replay.
- bug_marker: "DISPATCH=VECTOR_V_ZBB_ZVKB"
- pre_marker: "DISPATCH=ZBB_ZVKB_NOVEC"
- benign_marker: "DISPATCH=C_SCALAR"
- target execution: run_poc confirmed on all three built versions with the identical /poc/run.sh: pre_intro -> DISPATCH=ZBB_ZVKB_NOVEC, post_intro -> DISPATCH=VECTOR_V_ZBB_ZVKB, post_benign -> DISPATCH=C_SCALAR. post_intro's chacha_riscv.c (commit 03ce37e11729) guards ChaCha20_ctr32_v_zbb_zvkb/ChaCha20_ctr32_v_zbb only with `len > CHACHA_BLK_SIZE && RISCV_HAS_ZBB() && riscv_vlen() >= 128` (no pointer-alignment test), so misaligned out/inp still get routed to the vector routine. post_benign's chacha_riscv.c (fix 22417bc14d6b content) adds `&& (size_t)out % sizeof(size_t) == 0 && (size_t)inp % sizeof(size_t) == 0` to that same guard, so the identical misaligned pointers are now routed to the safe C fallback. pre_intro's chacha_riscv.c (parent 7cbca5a6d6e7) does not yet contain the v_zbb/v_zbb_zvkb split at all; it unconditionally routes to a differently-named routine (ChaCha20_ctr32_zbb_zvkb, no 'v_' prefix) that is not the vector implementation this report concerns, so the specific missing-alignment-check flaw does not exist pre-intro.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=7cbca5a6d6e7  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=3f43ea64389e3bb8aac3f8411ca3093f652e1f54cfaf4a901d19699ba9aa4e67
  source_integrity=True
  output_tail:
    DISPATCH=ZBB_ZVKB_NOVEC
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=03ce37e11729  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=3f43ea64389e3bb8aac3f8411ca3093f652e1f54cfaf4a901d19699ba9aa4e67
  source_integrity=True
  output_tail:
    DISPATCH=VECTOR_V_ZBB_ZVKB
    VERIFY_EXIT=0
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=7cbca5a6d6e7  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=3f43ea64389e3bb8aac3f8411ca3093f652e1f54cfaf4a901d19699ba9aa4e67
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    DISPATCH=C_SCALAR
    VERIFY_EXIT=0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
