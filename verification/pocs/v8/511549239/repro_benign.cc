// Companion to repro_intro.cc: exercises the FIXED CanInlineCall API from
// commit 63226679f9f5 on the exact same "no MaglevGraphLabeller" graph, with
// an unknown (nullptr) current_unit -- the analogous "we don't know what
// unit this call site came from" situation that used to dereference
// current_provenance().unit unconditionally. The fixed signature takes an
// explicit (possibly-null) MaglevCompilationUnit* and null-checks it before
// dereferencing, so this must NOT crash.

#include <cstdio>
#include <memory>

#include "include/v8-context.h"
#include "include/v8-initialization.h"
#include "include/v8-isolate.h"
#include "include/v8-local-handle.h"
#include "include/v8-script.h"
#include "include/v8-template.h"
#include "include/libplatform/libplatform.h"

#include "src/api/api-inl.h"
#include "src/compiler/js-heap-broker.h"
#include "src/execution/isolate.h"
#include "src/execution/local-isolate.h"
#include "src/flags/flags.h"
#include "src/handles/persistent-handles.h"
#include "src/maglev/maglev-compilation-info.h"
#include "src/maglev/maglev-compilation-unit.h"
#include "src/maglev/maglev-graph-builder.h"
#include "src/maglev/maglev-graph-optimizer.h"
#include "src/maglev/maglev-graph.h"
#include "src/maglev/maglev-ir-inl.h"
#include "src/maglev/maglev-reducer-inl.h"
#include "src/objects/js-function-inl.h"

int main(int argc, char* argv[]) {
  v8::V8::InitializeICUDefaultLocation(argv[0]);
  std::unique_ptr<v8::Platform> platform = v8::platform::NewDefaultPlatform();
  v8::V8::InitializePlatform(platform.get());
  v8::V8::Initialize();

  v8::Isolate::CreateParams create_params;
  create_params.array_buffer_allocator =
      v8::ArrayBuffer::Allocator::NewDefaultAllocator();
  v8::Isolate* isolate = v8::Isolate::New(create_params);
  {
    v8::Isolate::Scope isolate_scope(isolate);
    v8::HandleScope handle_scope(isolate);
    v8::Local<v8::Context> context = v8::Context::New(isolate);
    v8::Context::Scope context_scope(context);

    const char* src = "function f(x) { return x + 1; } f(1); f;";
    v8::Local<v8::String> source =
        v8::String::NewFromUtf8(isolate, src).ToLocalChecked();
    v8::Local<v8::Script> script =
        v8::Script::Compile(context, source).ToLocalChecked();
    v8::Local<v8::Value> result = script->Run(context).ToLocalChecked();
    v8::Local<v8::Function> func = result.As<v8::Function>();

    i::Isolate* i_isolate = reinterpret_cast<i::Isolate*>(isolate);
    i::Handle<i::JSFunction> function =
        i::Cast<i::JSFunction>(v8::Utils::OpenHandle(*func));

    printf("[repro] function has bytecode array: %d\n",
           function->shared()->HasBytecodeArray() ? 1 : 0);
    fflush(stdout);

    auto info = i::maglev::MaglevCompilationInfo::New(
        i_isolate, function, i::BytecodeOffset::None());
    i::maglev::Graph* graph = i::maglev::Graph::New(info.get());
    i::compiler::CurrentHeapBrokerScope current_broker(info->broker());

    printf("[repro] has_graph_labeller=%d (expect 0)\n",
           graph->has_graph_labeller() ? 1 : 0);
    fflush(stdout);

    i::compiler::SharedFunctionInfoRef shared =
        i::compiler::MakeRef(info->broker(), function->shared());

    i::maglev::MaglevReducer<i::maglev::MaglevGraphOptimizer> reducer(
        nullptr, graph);

    printf("[repro] calling FIXED CanInlineCall(nullptr, shared, 1.0f) -- "
           "same call site, with an explicit-but-unknown current_unit, "
           "exactly as MaglevGraphOptimizer::VisitCall passes when the call "
           "node has no lazy deopt info...\n");
    fflush(stdout);

    const i::maglev::MaglevCompilationUnit* unknown_unit = nullptr;
    bool can_inline = reducer.CanInlineCall(unknown_unit, shared, 1.0f);

    printf("[repro] NO CRASH. CanInlineCall returned %d\n", can_inline ? 1 : 0);
    fflush(stdout);
  }
  printf("[repro] DONE\n");
  fflush(stdout);
  isolate->Dispose();
  return 0;
}
