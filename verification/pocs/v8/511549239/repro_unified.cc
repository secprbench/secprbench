// Unified harness for bug 511549239 (Maglev NullPointerDereference).
//
// The SAME source file and SAME invocation is used, unmodified, against
// pre_intro, post_intro and post_benign. MaglevReducer<BaseT>::CanInlineCall
// changed shape across these revisions (it didn't exist pre-intro; took
// (SharedFunctionInfoRef, float) in the buggy post_intro version; takes
// (const MaglevCompilationUnit*, SharedFunctionInfoRef, float) in the fixed
// post_benign version) -- that signature change is exactly what the intro
// and fix commits did, so this harness uses SFINAE to detect whichever
// overload the revision being tested actually has and calls it, letting the
// revision's own compiled code decide the outcome:
//   - pre_intro:    neither overload exists    -> prints "ABSENT", no call.
//   - post_intro:   2-arg (buggy) overload      -> calls it -> SEGV.
//   - post_benign:  3-arg (fixed) overload      -> calls it -> safe.
//
// In all cases the Graph is built the same way: MaglevGraphBuilder::Build()
// is called directly (bypassing MaglevCompiler::Compile), so no
// MaglevGraphLabeller is ever attached (has_graph_labeller() == 0) -- the
// "non-tracing, no --gdbjit" condition the fix commit message names as the
// trigger. (Reaching that condition from plain command-line d8/JS is
// defeated in this exact build because v8_flags.maglev_gdbjit is
// FLAG_READONLY and hard-defaults to true when ENABLE_GDB_JIT_INTERFACE is
// not compiled in, which unconditionally forces a graph labeller via the
// unguarded `|| v8_flags.maglev_gdbjit` clause present identically in
// pre_intro and post_intro -- itself one of the things commit 63226679f9f5
// also fixes.)

#include <cstdio>
#include <memory>
#include <type_traits>
#include <utility>

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

namespace {

using Reducer = i::maglev::MaglevReducer<i::maglev::MaglevGraphOptimizer>;
using Shared = i::compiler::SharedFunctionInfoRef;
using Unit = i::maglev::MaglevCompilationUnit;

// Prefer the 2-arg (buggy, post_intro) overload if it exists.
template <typename R>
auto TryTwoArg(R& reducer, Shared shared, float freq, int)
    -> decltype(reducer.CanInlineCall(shared, freq), true) {
  printf("[repro] found 2-arg CanInlineCall(shared, freq) -- this is the "
         "post_intro buggy signature. Calling it now...\n");
  fflush(stdout);
  bool result = reducer.CanInlineCall(shared, freq);
  printf("[repro] NO CRASH. CanInlineCall returned %d\n", result ? 1 : 0);
  fflush(stdout);
  return true;
}
template <typename R>
bool TryTwoArg(R&, Shared, float, long) {
  return false;
}

// Otherwise, try the 3-arg (fixed, post_benign) overload.
template <typename R>
auto TryThreeArg(R& reducer, Shared shared, float freq, int) -> decltype(
    reducer.CanInlineCall(static_cast<const Unit*>(nullptr), shared, freq),
    true) {
  printf("[repro] found 3-arg CanInlineCall(current_unit, shared, freq) -- "
         "this is the post_benign fixed signature. Calling it with "
         "current_unit=nullptr (unknown provenance) now...\n");
  fflush(stdout);
  bool result =
      reducer.CanInlineCall(static_cast<const Unit*>(nullptr), shared, freq);
  printf("[repro] NO CRASH. CanInlineCall returned %d\n", result ? 1 : 0);
  fflush(stdout);
  return true;
}
template <typename R>
bool TryThreeArg(R&, Shared, float, long) {
  return false;
}

}  // namespace

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

    auto info = i::maglev::MaglevCompilationInfo::New(
        i_isolate, function, i::BytecodeOffset::None());
    i::maglev::Graph* graph = i::maglev::Graph::New(info.get());
    i::compiler::CurrentHeapBrokerScope current_broker(info->broker());

    printf("[repro] has_graph_labeller=%d (expect 0: MaglevCompiler::Compile "
           "was never called)\n",
           graph->has_graph_labeller() ? 1 : 0);
    fflush(stdout);

    i::compiler::SharedFunctionInfoRef shared =
        i::compiler::MakeRef(info->broker(), function->shared());

    Reducer reducer(nullptr, graph);

    if (!TryTwoArg(reducer, shared, 1.0f, 0)) {
      if (!TryThreeArg(reducer, shared, 1.0f, 0)) {
        printf("[repro] ABSENT: MaglevReducer<MaglevGraphOptimizer> has no "
               "CanInlineCall overload at all on this revision (expected on "
               "pre_intro: the shared CanInlineCall + non-eager-inlining "
               "VisitCall promotion logic did not exist yet).\n");
        fflush(stdout);
      }
    }
  }
  printf("[repro] DONE\n");
  fflush(stdout);
  isolate->Dispose();
  return 0;
}
