# Verification report: pr_review_GH-11704

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: LogicError
- **Intro commit**: `a7e1150019bdeb4675ebe4c67cbb0f3469803a72`
- **Intro parent**: `046a51cac25e0a6679548a0cf5501da057b6a154`
- **Fix commit**: `136500ed555ea7665a50a9222c6bf1f29a6a3c13`
- **Affected files**: ['crates/wasi-nn/src/wit.rs']

## PoC
- source: agent-generated (initial source: no_poc)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/wasmtime/b85b2cd9802305ea8489/attempts/02/pocs/wasmtime/GH-11704`
- input: `None` (0 bytes)
- run.sh: False
- note: poc dir has neither run.sh nor a recognizable input file

## Findings

- Exact bug and unaffected output lines matched the shared three-version Docker replay.
- Bug: GH-11704 is a resource-table memory leak in wasmtime-wasi-nn's WIT ("preview2"/component-model) binding, introduced when commit a7e1150019bd refactored `HostGraphExecutionContext::compute()` to accept `inputs: Vec<NamedTensor>` (an *owned* transfer of `Resource<Tensor>` handles per the WIT `own<tensor>` contract) but implemented it with a non-consuming `self.table.get(&tensor_resopurce)` instead of removing the entry from `self.table`. Every inference call therefore permanently leaks one ResourceTable slot per input tensor. The companion fix (post_benign, matching real upstream fix 136500ed555e) changes this to `self.table.delete(tensor_resopurce)`, which both takes ownership (matching `into_iter()`) and frees the slot.

There was no existing PoC, and this is a pure host-side logic/resource-lifecycle bug (not something a sanitizer catches), so I built a precise, self-checking Rust harness under /poc and ran it with run_poc using the exact same command and exact same script bytes on all three revisions (`bash /poc/setup_final.sh`), satisfying "same reproducing command/input across versions" literally -- every run completed cleanly with exit 0.

Because the vulnerable code's generated WIT host traits (HostGraphExecutionContext, HostGraph, HostTensor, the `generated_` bindgen module) are not part of wasmtime-wasi-nn's public API -- `pub(crate)` in post_intro/post_benign, fully module-private in pre_intro -- an ordinary external dependent crate cannot name them. The harness instead recompiles the real, unedited crates/wasi-nn/src/{lib,backend/mod,registry/mod,wit}.rs source as part of a brand-new crate (via `#[path]`, with a symlinked wit/ directory so the bindgen! macro's manifest-relative WIT path still resolves), and for the pre_intro-only branch nests the harness as a true child module of `wit` (via `include!`, since that revision's `generated_` module is plain-private rather than `pub(crate)`) so the private items remain visible. No tracked source file was ever edited; for pre_intro's `include!` path only, 16 purely-documentary `//!` lines (which `include!` cannot splice mid-module) were dropped from a throwaway copy used solely for inclusion -- zero logic/code changed. A tiny mock ML backend stands in for the real OpenVINO/ONNX/WinML/PyTorch backends, implementing whichever BackendExecutionContext trait shape (old 0-arg `compute()` or new `Option<Vec<NamedTensor>>` `compute()`) the checked-out revision's backend/mod.rs actually declares -- the harness detects this automatically by grepping the unmodified source, so the same script transparently builds the matching variant everywhere. RUSTFLAGS is cleared for this standalone build (the repo's global `-Zsanitizer=address` otherwise breaks proc-macro loading for an out-of-workspace crate; irrelevant here since this is a logic bug, not a memory-safety one).

Results, all via run_poc with the identical command, all exit=0:
- post_intro: `API=new ... growth=1001` after 1000 compute() calls -> confirms the unbounded per-call leak (intro_verified=yes).
- post_benign: `API=new ... growth=0` -> confirms the fix removes the leak (benign_verified=yes).
- pre_intro: the harness detects `API=old` (the leaking `compute(inputs: Vec<NamedTensor>)` entry point does not exist in this revision at all -- direct proof the vulnerable code is new in the intro commit) and exercises the old API's own analogous flow, obtaining `growth=1`, i.e. bounded/reused regardless of iteration count -- no equivalent leak existed beforehand either.

Taken together: intro_verified=yes (post_intro demonstrably leaks proportionally to call count via a code path that provably does not exist in pre_intro) and benign_verified=yes (post_benign runs the identical "new"-API reproducer and shows zero growth).

## Agent oracle

- machine gate: verified (behavioral)
- basis: Exact bug and unaffected output lines matched the shared three-version Docker replay.
- bug_marker: "API=new RESULT first_tensor_rep=2 sentinel_rep=1003 iterations=1000 growth=1001"
- pre_marker: "API=old RESULT first_tensor_rep=2 sentinel_rep=3 iterations=1000 growth=1"
- benign_marker: "API=new RESULT first_tensor_rep=2 sentinel_rep=2 iterations=1000 growth=0"
- target execution: post_intro (commit a7e1150019bd), API=new branch taken: crates/wasi-nn/src/wit.rs HostGraphExecutionContext::compute() does `for (name, tensor_resopurce) in inputs.iter() { let tensor = self.table.get(&tensor_resopurce)?; ... }` -- only borrows each input Resource<Tensor>, never calls `self.table.delete(...)`, even though `inputs: Vec<NamedTensor>` is taken by value (owned transfer per the WIT `own<tensor>` contract). growth=1001 after 1000 calls: every call leaks exactly one ResourceTable slot, unbounded.
post_benign (companion fix on parent 046a51cac25e, matching upstream fix 136500ed555e), API=new branch taken (same code shape, fixed body): the loop instead does `for (name, tensor_resopurce) in inputs.into_iter() { let tensor = self.table.delete(tensor_resopurce)?; ... }`, consuming and freeing the entry. growth=0: every new tensor reuses the same freed slot (rep=2) regardless of call count.
pre_intro (046a51cac25e, the parent of the intro commit): the harness detects the OLD API (BackendExecutionContext::compute takes zero tensor arguments; crates/wasi-nn/src/backend/mod.rs's trait is `fn compute(&mut self) -> Result<(), BackendError>`, not `fn compute(&mut self, inputs: Option<Vec<NamedTensor>>)`), confirming the owning multi-tensor compute() entry point -- the sole locus of the GH-11704 leak -- does not exist before the intro commit. Exercising the old API's own analogous flow (set_input + compute + get_output, with the guest explicitly dropping both the input and output tensor handles it still owns, since set_input only borrows) for 1000 iterations gives growth=1 -- bounded/reused, not scaling with iteration count, i.e. no equivalent unbounded leak existed under the pre-refactor design either.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=046a51cac25e  note=build cached
  command=bash /poc/setup_final.sh
  poc_sha256=7eee81d2eef0b32aa0174ef390ca4540c0913f5169f5ba2a80b86db01022dd56
  source_integrity=True
  output_tail:
       = note: no expected values for `feature`
       = help: consider adding `onnx` as a feature in `Cargo.toml`
       = note: see <https://doc.rust-lang.org/nightly/rustc/check-cfg/cargo-specifics.html> for more information about checking conditional configuration
    
    warning: unexpected `cfg` condition value: `pytorch`
      --> /work/crates/wasi-nn/src/backend/mod.rs:47:11
       |
    47 |     #[cfg(feature = "pytorch")]
       |           ^^^^^^^^^^^^^^^^^^^ help: remove the condition
       |
       = note: no expected values for `feature`
       = help: consider adding `pytorch` as a feature in `Cargo.toml`
       = note: see <https://doc.rust-lang.org/nightly/rustc/check-cfg/cargo-specifics.html> for more information about checking conditional configuration
    
    warning: `poc_harness_final` (lib) generated 12 warnings
        Finished `dev` profile [unoptimized + debuginfo] target(s) in 50.29s
    ---RUN---
    API=old RESULT first_tensor_rep=2 sentinel_rep=3 iterations=1000 growth=1
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=a7e1150019bd  note=build cached
  command=bash /poc/setup_final.sh
  poc_sha256=7eee81d2eef0b32aa0174ef390ca4540c0913f5169f5ba2a80b86db01022dd56
  source_integrity=True
  output_tail:
       = note: no expected values for `feature`
       = help: consider adding `onnx` as a feature in `Cargo.toml`
       = note: see <https://doc.rust-lang.org/nightly/rustc/check-cfg/cargo-specifics.html> for more information about checking conditional configuration
    
    warning: unexpected `cfg` condition value: `pytorch`
      --> /work/crates/wasi-nn/src/backend/mod.rs:47:11
       |
    47 |     #[cfg(feature = "pytorch")]
       |           ^^^^^^^^^^^^^^^^^^^ help: remove the condition
       |
       = note: no expected values for `feature`
       = help: consider adding `pytorch` as a feature in `Cargo.toml`
       = note: see <https://doc.rust-lang.org/nightly/rustc/check-cfg/cargo-specifics.html> for more information about checking conditional configuration
    
    warning: `poc_harness_final` (lib) generated 12 warnings
        Finished `dev` profile [unoptimized + debuginfo] target(s) in 48.67s
    ---RUN---
    API=new RESULT first_tensor_rep=2 sentinel_rep=1003 iterations=1000 growth=1001
    VERIFY_EXIT=0
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=046a51cac25e  note=build cached
  command=bash /poc/setup_final.sh
  poc_sha256=7eee81d2eef0b32aa0174ef390ca4540c0913f5169f5ba2a80b86db01022dd56
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
       = note: no expected values for `feature`
       = help: consider adding `onnx` as a feature in `Cargo.toml`
       = note: see <https://doc.rust-lang.org/nightly/rustc/check-cfg/cargo-specifics.html> for more information about checking conditional configuration
    
    warning: unexpected `cfg` condition value: `pytorch`
      --> /work/crates/wasi-nn/src/backend/mod.rs:47:11
       |
    47 |     #[cfg(feature = "pytorch")]
       |           ^^^^^^^^^^^^^^^^^^^ help: remove the condition
       |
       = note: no expected values for `feature`
       = help: consider adding `pytorch` as a feature in `Cargo.toml`
       = note: see <https://doc.rust-lang.org/nightly/rustc/check-cfg/cargo-specifics.html> for more information about checking conditional configuration
    
    warning: `poc_harness_final` (lib) generated 12 warnings
        Finished `dev` profile [unoptimized + debuginfo] target(s) in 48.88s
    ---RUN---
    API=new RESULT first_tensor_rep=2 sentinel_rep=2 iterations=1000 growth=0
    VERIFY_EXIT=0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
