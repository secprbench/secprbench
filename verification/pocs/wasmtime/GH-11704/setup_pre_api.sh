set -e
rm -rf /tmp/poc_harness_pre
mkdir -p /tmp/poc_harness_pre/src
ln -sf /work/crates/wasi-nn/wit /tmp/poc_harness_pre/wit

# `include!` cannot splice inner (`//!`) doc comments at a non-file-root
# position. Those lines are pure documentation (no executable/logic content),
# so we drop them from a throwaway copy used only for text inclusion; the
# real tracked file is never modified, and every remaining line is byte-for-
# byte identical to the original.
grep -v '^//!' /work/crates/wasi-nn/src/wit.rs > /tmp/poc_harness_pre/wit_src.rs
echo "--- diff (doc-comment-only lines removed) ---"
diff /work/crates/wasi-nn/src/wit.rs /tmp/poc_harness_pre/wit_src.rs || true

cat > /tmp/poc_harness_pre/Cargo.toml <<'EOF'
[package]
name = "poc_harness_pre"
version = "0.1.0"
edition = "2024"

[lib]
path = "src/lib.rs"

[[bin]]
name = "harness"
path = "src/main.rs"

[dependencies]
anyhow = { version = "=1.0.93", features = ["std"] }
wiggle = { path = "/work/crates/wiggle", features = ["wasmtime"] }
wasmtime = { path = "/work/crates/wasmtime", features = ["component-model", "runtime", "std"] }
tracing = { version = "=0.1.37" }
thiserror = { version = "=1.0.65" }
serde = { version = "=1.0.215", features = ["derive"] }
EOF

cat > /tmp/poc_harness_pre/src/lib.rs <<'EOF'
#[path = "/work/crates/wasi-nn/src/backend/mod.rs"]
pub mod backend;
#[path = "/work/crates/wasi-nn/src/registry/mod.rs"]
mod registry;

// `wit.rs` declares its generated bindings module as plain `mod generated_`
// (module-private, not `pub(crate)`) in this pre-refactor revision. To reach
// it from our own harness code without editing the tracked file, we splice
// the unmodified file (sans top doc comments, see wit_src.rs) in textually
// via `include!` and nest our harness as a genuine child module of `wit`, to
// which private items remain visible.
pub mod wit {
    include!("/tmp/poc_harness_pre/wit_src.rs");

    pub mod harness {
        use super::generated_::wasi::nn::graph::{Host as GraphHost, HostGraph};
        use super::generated_::wasi::nn::inference::HostGraphExecutionContext;
        use super::generated_::wasi::nn::tensor::HostTensor;
        use super::{ExecutionTarget, GraphEncoding, TensorType, WasiNnCtx, WasiNnView};
        use crate::mock_backend::MockBackend;
        use crate::{Backend, InMemoryRegistry, Registry};
        use wasmtime::component::{Resource, ResourceTable};

        pub fn run(iterations: u32) -> String {
            let backend: Backend = MockBackend.into();
            let registry: Registry = InMemoryRegistry::new().into();
            let mut ctx = WasiNnCtx::new([backend], registry);
            let mut table = ResourceTable::new();
            let mut view = WasiNnView::new(&mut table, &mut ctx);

            let graph = GraphHost::load(
                &mut view,
                vec![vec![0u8]],
                GraphEncoding::Autodetect,
                ExecutionTarget::Cpu,
            )
            .expect("load call ok")
            .expect("load returned a graph");

            let exec = HostGraph::init_execution_context(&mut view, graph)
                .expect("init call ok")
                .expect("init returned a context");
            let exec_rep = exec.rep();

            let first_tensor = HostTensor::new(&mut view, vec![1], TensorType::Fp32, vec![0u8; 4])
                .expect("tensor new ok");
            let first_tensor_rep = first_tensor.rep();
            HostGraphExecutionContext::set_input(
                &mut view,
                Resource::new_own(exec_rep),
                "input".to_string(),
                first_tensor,
            )
            .expect("set_input call ok")
            .expect("set_input returned ok");
            HostGraphExecutionContext::compute(&mut view, Resource::new_own(exec_rep))
                .expect("compute call ok")
                .expect("compute returned ok");
            let out = HostGraphExecutionContext::get_output(
                &mut view,
                Resource::new_own(exec_rep),
                "output".to_string(),
            )
            .expect("get_output call ok")
            .expect("get_output returned ok");
            HostTensor::drop(&mut view, Resource::new_own(first_tensor_rep)).expect("drop ok");
            HostTensor::drop(&mut view, out).expect("drop ok");

            for _ in 0..iterations {
                let tensor = HostTensor::new(&mut view, vec![1], TensorType::Fp32, vec![0u8; 4])
                    .expect("tensor new ok");
                let tensor_rep = tensor.rep();
                HostGraphExecutionContext::set_input(
                    &mut view,
                    Resource::new_own(exec_rep),
                    "input".to_string(),
                    tensor,
                )
                .expect("set_input call ok")
                .expect("set_input returned ok");
                HostGraphExecutionContext::compute(&mut view, Resource::new_own(exec_rep))
                    .expect("compute call ok")
                    .expect("compute returned ok");
                let out = HostGraphExecutionContext::get_output(
                    &mut view,
                    Resource::new_own(exec_rep),
                    "output".to_string(),
                )
                .expect("get_output call ok")
                .expect("get_output returned ok");
                HostTensor::drop(&mut view, Resource::new_own(tensor_rep)).expect("drop ok");
                HostTensor::drop(&mut view, out).expect("drop ok");
            }

            let sentinel = HostTensor::new(&mut view, vec![1], TensorType::Fp32, vec![0u8; 4])
                .expect("tensor new ok");
            let sentinel_rep = sentinel.rep();

            format!(
                "RESULT first_tensor_rep={} sentinel_rep={} iterations={} growth={}",
                first_tensor_rep,
                sentinel_rep,
                iterations,
                sentinel_rep as i64 - first_tensor_rep as i64
            )
        }
    }
}

use anyhow::anyhow;
use core::fmt;
pub use registry::{GraphRegistry, InMemoryRegistry};
use std::path::Path;
use std::sync::Arc;

pub fn preload(preload_graphs: &[(String, String)]) -> anyhow::Result<(Vec<Backend>, Registry)> {
    let mut backends = backend::list();
    let mut registry = InMemoryRegistry::new();
    for (kind, path) in preload_graphs {
        let kind_ = kind.parse()?;
        let backend = backends
            .iter_mut()
            .find(|b| b.encoding() == kind_)
            .ok_or(anyhow!("unsupported backend: {}", kind))?
            .as_dir_loadable()
            .ok_or(anyhow!("{} does not support directory loading", kind))?;
        registry.load(backend, Path::new(path))?;
    }
    Ok((backends, Registry::from(registry)))
}

pub struct Backend(Box<dyn backend::BackendInner>);
impl std::ops::Deref for Backend {
    type Target = dyn backend::BackendInner;
    fn deref(&self) -> &Self::Target {
        self.0.as_ref()
    }
}
impl std::ops::DerefMut for Backend {
    fn deref_mut(&mut self) -> &mut Self::Target {
        self.0.as_mut()
    }
}
impl<T: backend::BackendInner + 'static> From<T> for Backend {
    fn from(value: T) -> Self {
        Self(Box::new(value))
    }
}

#[derive(Clone)]
pub struct Graph(Arc<dyn backend::BackendGraph>);
impl From<Box<dyn backend::BackendGraph>> for Graph {
    fn from(value: Box<dyn backend::BackendGraph>) -> Self {
        Self(value.into())
    }
}
impl std::ops::Deref for Graph {
    type Target = dyn backend::BackendGraph;
    fn deref(&self) -> &Self::Target {
        self.0.as_ref()
    }
}

#[derive(Clone, PartialEq)]
pub struct Tensor {
    pub dimensions: Vec<u32>,
    pub ty: wit::TensorType,
    pub data: Vec<u8>,
}
impl fmt::Debug for Tensor {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("Tensor")
            .field("dimensions", &self.dimensions)
            .field("ty", &self.ty)
            .field("data (bytes)", &self.data.len())
            .finish()
    }
}

pub struct ExecutionContext(Box<dyn backend::BackendExecutionContext>);
impl From<Box<dyn backend::BackendExecutionContext>> for ExecutionContext {
    fn from(value: Box<dyn backend::BackendExecutionContext>) -> Self {
        Self(value)
    }
}
impl std::ops::Deref for ExecutionContext {
    type Target = dyn backend::BackendExecutionContext;
    fn deref(&self) -> &Self::Target {
        self.0.as_ref()
    }
}
impl std::ops::DerefMut for ExecutionContext {
    fn deref_mut(&mut self) -> &mut Self::Target {
        self.0.as_mut()
    }
}

pub struct Registry(Box<dyn GraphRegistry>);
impl std::ops::Deref for Registry {
    type Target = dyn GraphRegistry;
    fn deref(&self) -> &Self::Target {
        self.0.as_ref()
    }
}
impl std::ops::DerefMut for Registry {
    fn deref_mut(&mut self) -> &mut Self::Target {
        self.0.as_mut()
    }
}
impl<T> From<T> for Registry
where
    T: GraphRegistry + 'static,
{
    fn from(value: T) -> Self {
        Self(Box::new(value))
    }
}

pub mod mock_backend {
    use crate::backend::{BackendError, BackendExecutionContext, BackendFromDir, BackendGraph, BackendInner, Id};
    use crate::wit::{ExecutionTarget, GraphEncoding};
    use crate::{ExecutionContext, Graph, Tensor};

    #[derive(Default)]
    pub struct MockBackend;
    impl BackendInner for MockBackend {
        fn encoding(&self) -> GraphEncoding {
            GraphEncoding::Autodetect
        }
        fn load(&mut self, _builders: &[&[u8]], _target: ExecutionTarget) -> Result<Graph, BackendError> {
            Ok(Graph::from(Box::new(MockGraph) as Box<dyn BackendGraph>))
        }
        fn as_dir_loadable<'a>(&'a mut self) -> Option<&'a mut dyn BackendFromDir> {
            None
        }
    }

    pub struct MockGraph;
    impl BackendGraph for MockGraph {
        fn init_execution_context(&self) -> Result<ExecutionContext, BackendError> {
            Ok(ExecutionContext::from(Box::new(MockExecCtx) as Box<dyn BackendExecutionContext>))
        }
    }

    pub struct MockExecCtx;
    impl BackendExecutionContext for MockExecCtx {
        fn set_input(&mut self, _id: Id, _tensor: &Tensor) -> Result<(), BackendError> {
            Ok(())
        }
        fn compute(&mut self) -> Result<(), BackendError> {
            Ok(())
        }
        fn get_output(&mut self, _id: Id) -> Result<Tensor, BackendError> {
            Ok(Tensor { dimensions: vec![1], ty: crate::wit::TensorType::Fp32, data: vec![0, 0, 0, 0] })
        }
    }
}
EOF

cat > /tmp/poc_harness_pre/src/main.rs <<'EOF'
fn main() {
    println!("{}", poc_harness_pre::wit::harness::run(1000));
}
EOF

cd /tmp/poc_harness_pre
RUSTFLAGS='' cargo build --offline 2>&1 | tail -250
echo "---RUN---"
RUSTFLAGS='' ./target/debug/harness
