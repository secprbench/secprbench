// Data race PoC: WasmModule::signature_storage (WasmModuleSignatureStorage)
// is written during wasm instantiation when storing the signature of a V8
// "fast API call" import, but WasmModule::EstimateStoredSize() /
// EstimateCurrentMemoryConsumption() reads it without taking the
// NativeModule::allocation_mutex_ lock in the buggy revision (fixed in
// e194d3a40d8e; see discussion.md for the fixing commit message).
//
// Reader side: `%EstimateCurrentMemoryConsumption()` is a test-only V8
// runtime intrinsic (src/runtime/runtime-test-wasm.cc) that calls
// `wasm::GetWasmEngine()->EstimateCurrentMemoryConsumption()`, which walks
// every NativeModule currently known to the engine (process-wide, across
// all isolates) and calls `native_module->EstimateCurrentMemoryConsumption()`
// on each -- the exact lock-less read path that races with instantiation in
// the buggy revision. Dedicated reader workers hammer it continuously for
// the whole test's duration (time-bounded loop).
//
// Writer side: each module imports NUM_IMPORTS distinct functions sharing
// one wasm signature, so a single instantiate() call performs NUM_IMPORTS
// separate, lock-protected `signature_storage.Allocate()` calls that keep
// growing the storage's backing `std::vector<std::vector<uint8_t>>` (many
// push_back/reallocation events). Running several writer workers against
// the SAME fresh module at once serializes those Allocate() calls through
// NativeModule::allocation_mutex_, stretching the mutation phase into a
// wall-clock window that the lock-free readers get many chances to land
// inside of. Writers (and the main thread) GC right after each round so
// stale NativeModules don't pile up and keep the engine-wide scan cheap.

d8.file.execute('test/mjsunit/wasm/wasm-module-builder.js');

const NUM_IMPORTS = 2000;

function freshModule() {
  const builder = new WasmModuleBuilder();
  const sig = makeSig([kWasmExternRef, kWasmExternRef], [kWasmI32]);
  const importIndices = [];
  for (let i = 0; i < NUM_IMPORTS; i++) {
    importIndices.push(builder.addImport('mod', 'foo' + i, sig));
  }
  builder.addFunction('main', sig)
      .addBody([
        kExprLocalGet, 0,
        kExprLocalGet, 1,
        kExprCallFunction, importIndices[0],
      ])
      .exportFunc();
  return builder.toModule();
}

const NUM_WRITERS = 8;
const NUM_READERS = 16;
const ROUNDS = 80;
const READER_DURATION_MS = 180000;  // generous cap; terminate()d earlier.

const writerScript = `
  const fast_c_api = new d8.test.FastCAPI();
  const boundImport =
      Function.prototype.call.bind(fast_c_api.is_fast_c_api_object);
  const imports = {};
  for (let i = 0; i < ${NUM_IMPORTS}; i++) imports['foo' + i] = boundImport;
  onmessage = function(e) {
    const wasmModule = e.data;
    try {
      const instance =
          new WebAssembly.Instance(wasmModule, {'mod': imports});
    } catch (err) {
    }
    gc();
    postMessage('ack');
  };
`;

const readerScript = `
  onmessage = function(e) {
    const durationMs = e.data;
    const start = performance.now();
    let count = 0;
    while (performance.now() - start < durationMs) {
      try { %EstimateCurrentMemoryConsumption(); } catch (err) { break; }
      count++;
    }
    postMessage(count);
  };
`;

const writers = [];
for (let i = 0; i < NUM_WRITERS; i++) {
  writers.push(new Worker(writerScript, {type: 'string'}));
}
const readers = [];
for (let i = 0; i < NUM_READERS; i++) {
  readers.push(new Worker(readerScript, {type: 'string'}));
}

for (const r of readers) r.postMessage(READER_DURATION_MS);

for (let round = 0; round < ROUNDS; round++) {
  const t0 = performance.now();
  const wasmModule = freshModule();
  for (const w of writers) w.postMessage(wasmModule);
  for (const w of writers) w.getMessage();
  gc();
  if (round % 10 === 0) {
    print('round', round, 'done in', performance.now() - t0, 'ms');
  }
}

print('writer rounds finished; stopping readers');
for (const w of writers) w.terminate();
for (const r of readers) r.terminate();

print('PoC finished without detected error');
