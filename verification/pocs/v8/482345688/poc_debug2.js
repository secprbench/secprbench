d8.file.execute('test/mjsunit/wasm/wasm-module-builder.js');
const NUM_IMPORTS = 10;
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
print('fast_call_count', fast_c_api.fast_call_count());
for (let i = 0; i < 5; i++) gc();
print('done');
