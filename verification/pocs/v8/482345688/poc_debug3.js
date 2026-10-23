d8.file.execute('test/mjsunit/wasm/wasm-module-builder.js');
for (const NUM_IMPORTS of [10, 100, 500, 1000, 2000, 5000]) {
  const builder = new WasmModuleBuilder();
  const sig = makeSig([kWasmExternRef, kWasmExternRef], [kWasmI32]);
  const importIndices = [];
  for (let i = 0; i < NUM_IMPORTS; i++) {
    importIndices.push(builder.addImport('mod', 'foo' + i, sig));
  }
  builder.addFunction('main', sig)
      .addBody([kExprLocalGet, 0, kExprLocalGet, 1, kExprCallFunction, importIndices[0]])
      .exportFunc();
  const wasmModule = builder.toModule();
  const fast_c_api = new d8.test.FastCAPI();
  const boundImport = Function.prototype.call.bind(fast_c_api.is_fast_c_api_object);
  const imports = {};
  for (let i = 0; i < NUM_IMPORTS; i++) imports['foo' + i] = boundImport;
  const instance = new WebAssembly.Instance(wasmModule, {'mod': imports});
  instance.exports.main(fast_c_api, fast_c_api);
  print(NUM_IMPORTS, 'fast_call_count', fast_c_api.fast_call_count(), 'slow', fast_c_api.slow_call_count());
}
