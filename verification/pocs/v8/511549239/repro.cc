// Standalone harness: reproduces the Maglev NullPointerDereference described
// in bug 511549239 by building a Maglev graph directly (bypassing
// MaglevCompiler::Compile, so no MaglevGraphLabeller is installed) and then
// running the non-eager inliner's optimizer pass on a generic Call node
// whose target is a speculatively-constant-folded JSFunction (via
// Function.prototype.apply feedback), exactly the "non-eager inlining"
// direct-recursion-check path described in the fix commit.

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
#include "src/maglev/maglev-graph.h"
#include "src/maglev/maglev-inlining.h"
#include "src/maglev/maglev-ir-inl.h"
#include "src/objects/js-function.h"

int main(int argc, char* argv[]) {
  // Flags must be set before V8::Initialize() freezes the flag list.
  i::v8_flags.maglev_non_eager_inlining = true;
  i::v8_flags.max_maglev_inlined_bytecode_size_small = 0;
  i::v8_flags.max_maglev_inlined_bytecode_size = 20;
  i::v8_flags.lazy_feedback_allocation = false;
  i::v8_flags.trace_maglev_inlining = true;
  i::v8_flags.trace_maglev_graph_optimizer = true;

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

    const char* src =
        "var arr = [0];"
        "function other(x) {"
        "  let s = x;"
        "  s += x+1; s += x+2; s += x+3; s += x+4; s += x+5;"
        "  s += x+6; s += x+7; s += x+8; s += x+9; s += x+10;"
        "  s += x+11; s += x+12; s += x+13; s += x+14; s += x+15;"
        "  return s;"
        "}"
        "function recur(x) {"
        "  if (x <= 0) return other(x);"
        "  arr[0] = x - 1;"
        "  return recur.apply(null, arr);"
        "}"
        "for (let i = 0; i < 20; i++) { recur(5); }"
        "recur;";
    v8::Local<v8::String> source =
        v8::String::NewFromUtf8(isolate, src).ToLocalChecked();
    v8::Local<v8::Script> script =
        v8::Script::Compile(context, source).ToLocalChecked();
    v8::Local<v8::Value> result = script->Run(context).ToLocalChecked();
    v8::Local<v8::Function> func = result.As<v8::Function>();

    i::Isolate* i_isolate = reinterpret_cast<i::Isolate*>(isolate);
    i::Handle<i::JSFunction> function =
        i::Cast<i::JSFunction>(v8::Utils::OpenHandle(*func));

    printf("[repro] building Maglev graph directly (no MaglevCompiler::Compile)...\n");
    fflush(stdout);

    auto info = i::maglev::MaglevCompilationInfo::New(
        i_isolate, function, i::BytecodeOffset::None());
    i::maglev::Graph* graph = i::maglev::Graph::New(info.get());
    i::compiler::CurrentHeapBrokerScope current_broker(info->broker());
    i::maglev::MaglevGraphBuilder graph_builder(
        i_isolate->AsLocalIsolate(), info->toplevel_compilation_unit(), graph);
    i::PersistentHandlesScope persistent_scope(i_isolate);
    bool build_ok = graph_builder.Build();
    printf("[repro] has_graph_labeller=%d build_ok=%d\n",
           graph->has_graph_labeller() ? 1 : 0, build_ok ? 1 : 0);
    fflush(stdout);

    printf("[repro] ==== nodes after Build() ====\n");
    for (auto* block : graph->blocks()) {
      for (auto* node : block->nodes()) {
        printf("[repro] node opcode=%s\n",
               i::maglev::OpcodeToString(node->opcode()));
      }
    }
    fflush(stdout);

    if (build_ok) {
      printf("[repro] running MaglevInliner::Run() (non-eager inlining pass)...\n");
      fflush(stdout);
      i::maglev::MaglevInliner inliner(graph);
      bool run_ok = inliner.Run();
      printf("[repro] inliner.Run() ok=%d\n", run_ok ? 1 : 0);
      fflush(stdout);
    }
    printf("[repro] NO CRASH\n");
    fflush(stdout);
    persistent_scope.Detach();
  }
  printf("[repro] DONE\n");
  fflush(stdout);
  isolate->Dispose();
  return 0;
}
