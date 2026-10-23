let wat = `(module
  (type $arr (array (mut i16)))
  (func $fromCharCodeArray
    (import "wasm:js-string" "fromCharCodeArray")
    (param (ref null $arr) i32 i32)
    (result (ref extern)))
  (func (export "test") (result externref)
    (call $fromCharCodeArray
      (array.new $arr (i32.const 0x41) (i32.const 50))
      (i32.const 0)
      (i32.const 50)))
)`;

let bytes = wasmTextToBinary(wat);
let mod = new WebAssembly.Module(bytes, {builtins: ['js-string']});
let inst = new WebAssembly.Instance(mod, {}).exports;

let N = parseInt(scriptArgs[0]);
oomAtAllocation(N);
try {
  inst.test();
  print("NOCRASH_AT_" + N);
} catch (e) {
  print("JSEXC_AT_" + N + ": " + e);
}
resetOOMFailure();
