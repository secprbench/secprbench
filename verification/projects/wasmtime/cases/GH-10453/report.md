# Verification report: pr_review_GH-10453

- **Status**: `inconclusive`
- **Intro verified**: None
- **Benign verified**: None
- **Bug type**: OutOfBoundsRead
- **Intro commit**: `0a29578f1095679b7b1a84c486cfc338b0b87e7e`
- **Intro parent**: `406d00bb5afe8e361d90bf6699657f476bb566f6`
- **Fix commit**: `04eee21826057ca0f67ad55bd6386ce61d2352ce`
- **Affected files**: ['crates/cranelift/src/gc/enabled/drc.rs', 'crates/cranelift/src/gc/enabled.rs', 'crates/cranelift/src/gc/enabled/null.rs']

## PoC
- source: agent-final (initial source: poc-watch)
- dir: `/research-data/secprbench/season100-balanced-20261001/verification/cases/wasmtime/11a18f55feb5d7c62cdf/attempts/01/pocs/wasmtime/GH-10453`
- input: `array-new-fixed-of-gc-refs.wat` (7928 bytes)
- run.sh: True

## Findings

- The agent claim lacks a matching admissible three-version oracle.
- The intro commit (0a29578f) changed `DrcCompiler::alloc_array` (crates/cranelift/src/gc/enabled/drc.rs) to compute `num_gc_refs` for GC-ref-element arrays by reusing the `size` SSA value from `emit_array_size` (the array's total byte size including header) instead of the element count, packing this wrong value into the object's header reserved bits. That field is read back in the DRC collector's `trace_gc_ref` (crates/wasmtime/src/runtime/vm/gc/enabled/drc.rs) to bound a byte-slice of the object enumerating its outgoing GC-ref edges whenever the object's refcount hits zero. Since the stored value is the byte size rather than the element count, the computed slice end overruns the object's real allocation — an out-of-bounds read matching the OutOfBoundsRead label (caught here as a Rust slice-bounds panic rather than raw memory corruption only because Rust's safe indexing interposes a bounds check before any unsafe byte access/pointer interpretation of the overrun region occurs) — reliably triggered whenever a Wasm module allocates and lets a GC-ref array get collected.

This requires actually executing the Cranelift-JIT-compiled `array.new_fixed` instruction; the equivalent host-API call (`ArrayRef::new_fixed`, as used e.g. by tests/all/gc.rs's drc_transitive_drop_nested_arrays_tree) goes through a separate, correct, native computation of num_gc_refs and does not reproduce the bug — explaining why the deterministic fast-path reproduction did not crash on any revision. I built a small harness crate against the in-tree `wasmtime` library (ASan-instrumented via target-scoped RUSTFLAGS) that runs real Wasm bytecode performing the array allocation, roots and unroots the result, forces a GC, and converts any panic surfacing from the target's own GC code into a hard process abort, then ran it with run_poc unmodified across all three revisions:

- pre_intro (406d00bb): clean dealloc, no panic, exit 0 (`GC_DONE_NO_PANIC`) — object size 32, this header/tracing mechanism's current form didn't yet exist.
- post_intro (0a29578f): deterministic crash, exit 134 (SIGABRT), target panic `range end index 188 out of range for slice of length 40` at drc.rs:265:40 — exactly the labelled out-of-bounds read.
- post_benign (04eee218, the fix): clean dealloc, no panic, exit 0 (`GC_DONE_NO_PANIC`) — object size 40 matching post_intro, confirming num_gc_refs is now correctly 3 (not the byte size).

This cleanly establishes bug introduction at 0a29578f and resolution at 04eee218, using the identical reproducer across all three revisions via run_poc.

## Agent oracle

- machine gate: inconclusive (unproven)
- basis: The agent claim lacks a matching admissible three-version oracle.
- bug_marker: "TARGET PANIC (treated as crash): range end index 188 out of range for slice of length 40"
- pre_marker: "GC_DONE_NO_PANIC"
- benign_marker: "GC_DONE_NO_PANIC"
- target execution: run_poc(post_intro): exit=134, crashed=True. Output shows `CALL_OK`, `SCOPE_EXITED_NO_PANIC`, then `thread 'main' panicked at /work/crates/wasmtime/src/runtime/vm/gc/enabled/drc.rs:265:40: range end index 188 out of range for slice of length 40`, backtrace through `DrcHeap::dec_ref_and_maybe_dealloc` <- `GarbageCollection::collect` <- `GcStore::gc` <- `StoreOpaque::gc` <- `poc::main`, then our harness prints `TARGET PANIC (treated as crash): range end index 188 out of range for slice of length 40` and aborts (SIGABRT, exit 134). Earlier RUST_LOG=trace runs (identical scenario, same build) showed the array is allocated via `FreeList::alloc(Layout{size:40,..})`, ref count goes 1 (alloc) -> 2 (exposed to host on wasm->host return) -> 1 (RootScope exit) -> 0 (bump-chunk sweep during store.gc()), at which point the buggy num_gc_refs=40 (the object's own byte size, reused from `emit_array_size`'s `size` value in crates/cranelift/src/gc/enabled/drc.rs `alloc_array`) makes end_in_obj = start_in_obj(28) + 40*4 = 188, far exceeding the real 40-byte object, producing the panic. run_poc(pre_intro): exit=0, crashed=False, `FreeList::alloc(Layout{size:32,..})` (this header/tracing mechanism's current form predates this revision), clean dealloc, prints GC_DONE_NO_PANIC. run_poc(post_benign): exit=0, crashed=False, `FreeList::alloc(Layout{size:40,..})` (identical object size to post_intro), clean dealloc, prints GC_DONE_NO_PANIC, because num_gc_refs is correctly 3 (end_in_obj=28+3*4=40, exactly matching the real object length).

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=406d00bb5afe  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=1b3a1fd801ad4d426531f4c1ac3ea2cf6ad41c608eae59d52fcb8517ea5a86c0
  source_integrity=True
  output_tail:
       Compiling regex v1.9.1
       Compiling addr2line v0.24.1
       Compiling trait-variant v0.1.2
       Compiling memfd v0.6.4
       Compiling is-terminal v0.4.10
       Compiling wasmtime-jit-icache-coherence v32.0.0 (/work/crates/jit-icache-coherence)
       Compiling humantime v2.1.0
       Compiling once_cell v1.19.0
       Compiling sptr v0.3.2
       Compiling wasmtime-slab v32.0.0 (/work/crates/slab)
       Compiling env_logger v0.10.0
       Compiling poc v0.1.0 (/tmp/pocsrc_run)
        Finished `release` profile [optimized] target(s) in 1m 23s
    ===RUN===
    EXIT=0
    VERIFY_EXIT=0
    
    CALL_OK
    SCOPE_EXITED_NO_PANIC
    GC_DONE_NO_PANIC
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=0a29578f1095  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=1b3a1fd801ad4d426531f4c1ac3ea2cf6ad41c608eae59d52fcb8517ea5a86c0
  source_integrity=True
  crash_output:
       3: core::slice::index::slice_end_index_len_fail
       4: wasmtime::runtime::vm::gc::enabled::drc::DrcHeap::dec_ref_and_maybe_dealloc
       5: <wasmtime::runtime::vm::gc::enabled::drc::DrcCollection as wasmtime::runtime::vm::gc::gc_runtime::GarbageCollection>::collect_increment
       6: wasmtime::runtime::vm::gc::gc_runtime::GarbageCollection::collect
       7: wasmtime::runtime::vm::gc::GcStore::gc
       8: wasmtime::runtime::store::StoreOpaque::gc
       9: std::panicking::try::do_call
      10: __rust_try
      11: poc::main
    note: Some details are omitted, run with `RUST_BACKTRACE=full` for a verbose backtrace.
    TARGET PANIC (treated as crash): range end index 188 out of range for slice of length 40
    /poc/run.sh: line 10:  3786 Aborted                 RUST_LOG=wasmtime::runtime::vm::gc=trace /tmp/pocbuild_run/x86_64-unknown-linux-gnu/release/poc
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=406d00bb5afe  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=1b3a1fd801ad4d426531f4c1ac3ea2cf6ad41c608eae59d52fcb8517ea5a86c0
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
       Compiling regex v1.9.1
       Compiling addr2line v0.24.1
       Compiling trait-variant v0.1.2
       Compiling memfd v0.6.4
       Compiling is-terminal v0.4.10
       Compiling wasmtime-jit-icache-coherence v32.0.0 (/work/crates/jit-icache-coherence)
       Compiling humantime v2.1.0
       Compiling once_cell v1.19.0
       Compiling sptr v0.3.2
       Compiling wasmtime-slab v32.0.0 (/work/crates/slab)
       Compiling env_logger v0.10.0
       Compiling poc v0.1.0 (/tmp/pocsrc_run)
        Finished `release` profile [optimized] target(s) in 1m 21s
    ===RUN===
    EXIT=0
    VERIFY_EXIT=0
    
    CALL_OK
    SCOPE_EXITED_NO_PANIC
    GC_DONE_NO_PANIC
```

## Interpretation

The available evidence does not establish both labels. Inspect the findings and per-version results for the limiting reason.
