let wat = `(module
  (type $arr (array (mut i16)))
  (func $fromCharCodeArray
    (import "wasm:js-string" "fromCharCodeArray")
    (param (ref null $arr) i32 i32)
    (result (ref extern)))
  (func (export "test") (result externref)
    ;; 50 elements → bug writes 100 uint16_t (exceeds ~49-capacity Vector)
    (call $fromCharCodeArray
      (array.new $arr (i32.const 0x41) (i32.const 50))
      (i32.const 0)
      (i32.const 50)))
)`;

let bytes = wasmTextToBinary(wat);
let mod = new WebAssembly.Module(bytes, {builtins: ['js-string']});
let inst = new WebAssembly.Instance(mod, {}).exports;

// Force NoGC string allocation to fail at successive allocation points,
// but do NOT require that an exception is raised on failure (avoids an
// unrelated, pre-existing missing-OOM-report assertion on older revisions
// that lack the fallback path entirely).
oomTest(
    () => {
        inst.test()
    },
    false
);
print("done");
