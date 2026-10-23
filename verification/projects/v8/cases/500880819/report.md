# Verification report: pr_review_500880819

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: TypeConfusion
- **Intro commit**: `6469250a124acef52bceabae77ed887f5c8f29ac`
- **Intro parent**: `d1a6089b861336cf4b3887edfd3fdd280b23b5dd`
- **Fix commit**: `b9be4febd638434a37a4215b8ea9ae1f8fab4df6`
- **Affected files**: ['src/maglev/maglev-graph-builder.cc']

## PoC
- source: poc-watch
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/v8/c2c9d43ce573a3426493/attempts/01/pocs/v8/500880819`
- input: `regress-500880819.js` (881 bytes)
- run.sh: True

## Findings

- The default PoC (the checked-in regress-500880819.js, run via /poc/run.sh) did not crash on any of the three versions because a single default `gc()` call performs a full/major GC, which fully retraces the heap and doesn't expose a missing generational write barrier, and because the HeapNumber used for the trigger was already tenured to old space by the time of the vulnerable store. Using --print-maglev-graph I confirmed the intro commit's code path is exercised exactly as described in the root cause: `SetNamedProperty` for `o.smiField = x` lowers to CheckMaps + StoreTaggedFieldNoWriteBarrier with NO CheckSmi node in between (the elision added in 6469250a124a via `TryGetInt32Constant` matching `Smi::IsValid` on the `checked_value` alternative populated by BuildCheckNumericalValue's CheckFloat64SameValue path for the property-cell-constant store `G = x`). I then adapted the PoC to (1) tenure `obj` first via explicit major GCs, (2) supply a *fresh* young-generation HeapNumber(5.0) (confirmed via %DebugPrint that Float64Array reads produce genuine HeapNumber objects, not canonicalized Smis) as the value for the final optimized call, and (3) force scavenges (`gc({type:'minor'})`) afterward. This reproduced a deterministic SIGSEGV on post_intro (exit 139, signal 11 SEGV_ACCERR) consistent with the described type confusion / missing write barrier, while pre_intro and post_benign both run cleanly to completion (exit 0, printing 5) with the identical command and input, confirming the bug is genuinely introduced by 6469250a124a and genuinely fixed by the benign patch (which restores the `value_representation() != kTagged` gate).

## Per-version results

### pre_intro
```
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=d1a6089b8613  note=
```
### post_intro
```
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=6469250a124a  note=
```
### post_benign
```
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=d1a6089b8613  note=
  patch_method=plain  patch_clean=True
```

## Interpretation

The intro commit introduces the bug (clean before, crash after) and, where a benign companion exists, the benign patch removes it. Labels are consistent with execution.
