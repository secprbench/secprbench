// Direct reproduction of the Maglev NullPointerDereference (bug 511549239).
//
// MaglevReducer<BaseT>::CanInlineCall (introduced by commit 551ade488094)
// unconditionally dereferences current_provenance().unit:
//
//   if (current_provenance().unit->shared_function_info().equals(shared)) {
//
// current_provenance().unit defaults to the compilation_unit passed to the
// MaglevReducer constructor (nullptr by default), and is only ever updated
// from a registered node's provenance when the Graph has a
// MaglevGraphLabeller attached. MaglevGraphOptimizer (used by the non-eager
// inliner) constructs its MaglevReducer with no explicit compilation_unit
// (see MaglevGraphOptimizer::MaglevGraphOptimizer: `reducer_(this, graph)`),
// so whenever the Graph has no MaglevGraphLabeller (the normal case when
// --gdbjit and graph tracing are both off), current_provenance().unit stays
// null for the whole compile, and this call segfaults for *any* call
// processed by the non-eager inlining optimizer pass.
//
// This harness demonstrates that directly: it builds a real Maglev Graph for
// an actual JSFunction (bypassing MaglevCompiler::Compile, so no
// MaglevGraphLabeller is attached -- exactly the "non-tracing release build"
// condition from the fix commit message), then calls the exact same
// MaglevReducer<MaglevGraphOptimizer>::CanInlineCall entry point that
// MaglevGraphOptimizer::VisitCall calls during non-eager inlining.

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

    // Actually call f() once so it has a compiled BytecodeArray (required
    // before Maglev can build a graph for it).
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

    printf("[repro] has_graph_labeller=%d (expect 0: MaglevCompiler::Compile "
           "was never called, so no MaglevGraphLabeller is attached -- the "
           "'non-tracing, no --gdbjit' condition from the fix commit)\n",
           graph->has_graph_labeller() ? 1 : 0);
    fflush(stdout);

    i::compiler::SharedFunctionInfoRef shared =
        i::compiler::MakeRef(info->broker(), function->shared());

    printf("[repro] constructing MaglevReducer<MaglevGraphOptimizer> exactly "
           "like MaglevGraphOptimizer's own constructor does "
           "(reducer_(this, graph) -- no explicit compilation_unit, so "
           "current_provenance().unit defaults to nullptr)...\n");
    fflush(stdout);

    i::maglev::MaglevReducer<i::maglev::MaglevGraphOptimizer> reducer(
        nullptr, graph);

    printf("[repro] calling CanInlineCall(shared, 1.0f) -- the exact entry "
           "point MaglevGraphOptimizer::VisitCall uses during non-eager "
           "inlining to decide whether a newly-discovered call target is "
           "direct recursion...\n");
    fflush(stdout);

    bool can_inline = reducer.CanInlineCall(shared, 1.0f);

    printf("[repro] NO CRASH. CanInlineCall returned %d\n", can_inline ? 1 : 0);
    fflush(stdout);
  }
  printf("[repro] DONE\n");
  fflush(stdout);
  isolate->Dispose();
  return 0;
}
