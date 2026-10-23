use std::panic;
use wasmtime::*;

const WAT: &str = r#"
(module
  (type $ty (array (mut anyref)))
  (func (export "make") (param anyref anyref anyref) (result (ref $ty))
    (array.new_fixed $ty 3 (local.get 0) (local.get 1) (local.get 2))
  )
)
"#;

fn run() -> anyhow::Result<()> {
    let mut config = Config::new();
    config.wasm_function_references(true);
    config.wasm_gc(true);
    config.collector(Collector::DeferredReferenceCounting);

    let engine = Engine::new(&config)?;
    let module = Module::new(&engine, WAT)?;
    let mut store = Store::new(&engine, ());
    let instance = Instance::new(&mut store, &module, &[])?;
    let make = instance.get_func(&mut store, "make").unwrap();

    {
        let mut scope = RootScope::new(&mut store);
        let args = [Val::AnyRef(None), Val::AnyRef(None), Val::AnyRef(None)];
        let mut results = [Val::I32(0)];
        make.call(&mut scope, &args, &mut results)?;
        eprintln!("CALL_OK");
    }
    eprintln!("SCOPE_EXITED_NO_PANIC");

    // Drive the activation-table-held reference to zero, which is where the
    // DRC collector's transitive dec-ref tracing (over the JIT-allocated
    // array's bogus `num_gc_refs`, i.e. byte-size instead of element-count)
    // gets exercised.
    store.gc();
    eprintln!("GC_DONE_NO_PANIC");

    Ok(())
}

fn main() {
    // Any panic from inside the target's GC collection logic is a genuine
    // memory-safety-relevant defect (an out-of-bounds slice computed from a
    // corrupted header field embedded by compiled Wasm code). Turn it into a
    // hard process abort (SIGABRT) rather than a caught/unwound panic, so
    // that this is unambiguously reported as a crash rather than a clean
    // exit, without changing the crate's panic strategy (which otherwise
    // perturbs codegen/sanitizer instrumentation of unrelated code).
    let result = panic::catch_unwind(|| run());
    match result {
        Ok(Ok(())) => {}
        Ok(Err(e)) => {
            eprintln!("harness error (not the target bug): {e:?}");
            std::process::exit(2);
        }
        Err(payload) => {
            let msg = payload
                .downcast_ref::<String>()
                .map(|s| s.as_str())
                .or_else(|| payload.downcast_ref::<&str>().copied())
                .unwrap_or("<non-string panic payload>");
            eprintln!("TARGET PANIC (treated as crash): {msg}");
            std::process::abort();
        }
    }
}
