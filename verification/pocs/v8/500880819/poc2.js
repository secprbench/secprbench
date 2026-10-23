// Flags: --allow-natives-syntax --maglev --expose-gc

function makeHN(v) { let f = new Float64Array(1); f[0] = v; return f[0]; }

let obj = { smiField: 1 };
obj.smiField = 2;
obj.smiField = 3;

let HN5 = makeHN(5);
globalThis.G = HN5;

function sh(o, x, c) { if (c) o.smiField = x; }
function corrupt(o, x, c) { G = x; sh(o, x, c); }

%PrepareFunctionForOptimization(sh);
%PrepareFunctionForOptimization(corrupt);
sh(obj, 5, true);
corrupt(obj, HN5, false);
corrupt(obj, HN5, false);
%OptimizeMaglevOnNextCall(sh);
%OptimizeMaglevOnNextCall(corrupt);

// Ensure obj is promoted to old space.
gc();
gc();

// Fresh HeapNumber, still young generation.
let freshHN = makeHN(5);

// Trigger: HeapNumber(5.0) stored into kSmi-typed field without a Smi/tag
// check and without a write barrier (StoreTaggedFieldNoWriteBarrier).
corrupt(obj, freshHN, true);

// Force a scavenge: if the write barrier was skipped, obj's field still
// points at freshHN's pre-scavenge (now stale) location.
gc({type: 'minor'});
gc({type: 'minor'});

print(obj.smiField);
assertEquals(5, obj.smiField);
