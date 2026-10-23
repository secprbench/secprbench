d8.file.execute('test/mjsunit/wasm/wasm-module-builder.js');

const builder = new WasmModuleBuilder();
const sig = makeSig([kWasmExternRef, kWasmExternRef], [kWasmI32]);
const imp_index = builder.addImport('mod', 'foo', sig);
builder.addFunction('main', sig)
    .addBody([
      kExprLocalGet, 0,
      kExprLocalGet, 1,
      kExprCallFunction, imp_index,
    ])
    .exportFunc();

const wasmModule = builder.toModule();

const fast_c_api = new d8.test.FastCAPI();
const boundImport = Function.prototype.call.bind(fast_c_api.is_fast_c_api_object);
const instance = new WebAssembly.Instance(wasmModule, {'mod': {'foo': boundImport}});
fast_c_api.reset_counts();
print('result', instance.exports.main(fast_c_api, fast_c_api));
print('fast_call_count', fast_c_api.fast_call_count());
print('slow_call_count', fast_c_api.slow_call_count());
