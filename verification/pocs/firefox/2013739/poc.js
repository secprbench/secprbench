"use strict";

// GC trigger: pure JS allocation pressure fills nursery
function triggerGCviaAlloc() {
  let junk = [];
  for (let i = 0; i < 50000; i++) {
    junk.push({a: i, b: i + 1, c: [i, i + 1, i + 2]});
  }
  return junk.length;
}

const wat = `
(module
  (type $i32arr (array (mut i32)))
  (import "env" "triggerGC" (func $triggerGC (result i32)))

  ;; 32 i32 elements = 128 bytes data > 112 (MaxInlineBytes) => OOL
  ;; OOL block = 136 bytes <= 256 (MaxNurseryTrailerSize) => nursery-direct
  (func (export "test") (result i32)
    (local $arr (ref $i32arr))
    (local.set $arr (array.new $i32arr (i32.const 0) (i32.const 32)))
    (array.set $i32arr (local.get $arr) (i32.const 0) (i32.const 0xCAFEBABE))
    (array.set $i32arr (local.get $arr) (i32.const 1) (i32.const 0xDEADBEEF))
    (array.set $i32arr (local.get $arr) (i32.const 15) (i32.const 0xBAADF00D))
    (array.set $i32arr (local.get $arr) (i32.const 31) (i32.const 0x1337C0DE))
    ;; GC safepoint: Ion keeps data pointer live across this call
    (drop (call $triggerGC))
    ;; Reads via (potentially stale) data pointer
    (i32.add
      (i32.add
        (array.get $i32arr (local.get $arr) (i32.const 0))
        (array.get $i32arr (local.get $arr) (i32.const 1)))
      (i32.add
        (array.get $i32arr (local.get $arr) (i32.const 15))
        (array.get $i32arr (local.get $arr) (i32.const 31))))
  )
)`;

const binary = wasmTextToBinary(wat);
const mod = new WebAssembly.Module(binary);
const inst = new WebAssembly.Instance(mod, {
  env: { triggerGC: triggerGCviaAlloc }
});

const expected = (0xCAFEBABE + 0xDEADBEEF + 0xBAADF00D + 0x1337C0DE) | 0;

print("Phase 1: warmup for Ion tier-up...");
for (let i = 0; i < 2000; i++) {
  inst.exports.test();
}
print("Phase 2: GC pressure after Ion tier-up...");
for (let i = 0; i < 50; i++) {
  try {
    let r = inst.exports.test();
    if (r !== expected) {
      print("CORRUPTION at iter " + i + ": 0x" + (r >>> 0).toString(16));
      break;
    }
  } catch(e) {
    print("CRASH at iter " + i + ": " + e);
    break;
  }
}
print("Done.");
