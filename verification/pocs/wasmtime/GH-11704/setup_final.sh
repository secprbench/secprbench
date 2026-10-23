set -e
rm -rf /tmp/poc_harness_final
mkdir -p /tmp/poc_harness_final/src
ln -sf /work/crates/wasi-nn/wit /tmp/poc_harness_final/wit

# This single script is run with the exact same command on every revision
# (pre_intro / post_intro / post_benign). It detects -- purely by inspecting
# the unmodified target source it is about to recompile -- whether this
# revision's wasi-nn WIT `compute()` entry point takes ownership of a
# Vec<NamedTensor> of input tensors (the post-refactor "new" API, where the
# GH-11704 leak lives) or the pre-refactor "old" API (separate set-input /
# compute-with-no-args / get-output calls). It then builds and runs the
# matching variant of an identical resource-table growth oracle: create N
# tensors one at a time, run inference with each, and see whether the
# ResourceTable index of a final "sentinel" tensor push shows the table grew
# by N (leak) or stayed flat/reused (no leak).
if grep -q "inputs: Option<Vec<NamedTensor>>" /work/crates/wasi-nn/src/backend/mod.rs; then
  API=new
else
  API=old
fi
echo "DETECTED_API=${API}"

cat > /tmp/poc_harness_final/Cargo.toml <<'EOF'
[package]
name = "poc_harness_final"
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

if [ "$API" = "new" ]; then

cat > /tmp/poc_harness_final/src/lib.rs <<'EOF'
#[path = "/work/crates/wasi-nn/src/backend/mod.rs"]
pub mod backend;
#[path = "/work/crates/wasi-nn/src/registry/mod.rs"]
mod registry;
#[path = "/work/crates/wasi-nn/src/wit.rs"]
pub mod wit;

use crate::backend::{BackendError, Id, NamedTensor as BackendNamedTensor};
use crate::wit::generated_::wasi::nn::tensor::TensorType;
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
    pub ty: TensorType,
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

impl ExecutionContext {
    pub fn set_input(&mut self, id: Id, tensor: &Tensor) -> Result<(), BackendError> {
        self.0.set_input(id, tensor)
    }

    pub fn compute(&mut self) -> Result<(), BackendError> {
        self.0.compute(None).map(|_| ())
    }

    pub fn get_output(&mut self, id: Id) -> Result<Tensor, BackendError> {
        self.0.get_output(id)
    }

    pub fn compute_with_io(
        &mut self,
        inputs: Vec<BackendNamedTensor>,
    ) -> Result<Vec<BackendNamedTensor>, BackendError> {
        match self.0.compute(Some(inputs))? {
            Some(outputs) => Ok(outputs),
            None => Ok(Vec::new()),
        }
    }
}

impl Tensor {
    pub fn new(dimensions: Vec<u32>, ty: TensorType, data: Vec<u8>) -> Self {
        Self {
            dimensions,
            ty,
            data,
        }
    }
}

pub mod mock_backend {
    use crate::backend::{BackendError, BackendExecutionContext, BackendFromDir, BackendGraph, BackendInner, Id, NamedTensor};
    use crate::wit::generated_::wasi::nn::graph::{ExecutionTarget, GraphEncoding};
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
        fn get_output(&mut self, _id: Id) -> Result<Tensor, BackendError> {
            Ok(Tensor { dimensions: vec![1], ty: crate::wit::TensorType::Fp32, data: vec![0, 0, 0, 0] })
        }
        fn compute(&mut self, inputs: Option<Vec<NamedTensor>>) -> Result<Option<Vec<NamedTensor>>, BackendError> {
            let _ = inputs;
            Ok(Some(Vec::new()))
        }
    }
}

pub mod harness {
    use crate::mock_backend::MockBackend;
    use crate::wit::generated_::wasi::nn::graph::{ExecutionTarget, GraphEncoding, Host as GraphHost, HostGraph};
    use crate::wit::generated_::wasi::nn::inference::HostGraphExecutionContext;
    use crate::wit::generated_::wasi::nn::tensor::{HostTensor, TensorType};
    use crate::wit::{WasiNnCtx, WasiNnView};
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
        let _ = HostGraphExecutionContext::compute(
            &mut view,
            Resource::new_own(exec_rep),
            vec![("input".to_string(), first_tensor)],
        )
        .expect("compute call ok")
        .expect("compute returned ok");

        for _ in 0..iterations {
            let tensor = HostTensor::new(&mut view, vec![1], TensorType::Fp32, vec![0u8; 4])
                .expect("tensor new ok");
            let _ = HostGraphExecutionContext::compute(
                &mut view,
                Resource::new_own(exec_rep),
                vec![("input".to_string(), tensor)],
            )
            .expect("compute call ok")
            .expect("compute returned ok");
        }

        let sentinel = HostTensor::new(&mut view, vec![1], TensorType::Fp32, vec![0u8; 4])
            .expect("tensor new ok");
        let sentinel_rep = sentinel.rep();

        format!(
            "API=new RESULT first_tensor_rep={} sentinel_rep={} iterations={} growth={}",
            first_tensor_rep,
            sentinel_rep,
            iterations,
            sentinel_rep as i64 - first_tensor_rep as i64
        )
    }
}
EOF

else

grep -v '^//!' /work/crates/wasi-nn/src/wit.rs > /tmp/poc_harness_final/wit_src.rs

cat > /tmp/poc_harness_final/src/lib.rs <<'EOF'
#[path = "/work/crates/wasi-nn/src/backend/mod.rs"]
pub mod backend;
#[path = "/work/crates/wasi-nn/src/registry/mod.rs"]
mod registry;

pub mod wit {
    include!("/tmp/poc_harness_final/wit_src.rs");

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
                "API=old RESULT first_tensor_rep={} sentinel_rep={} iterations={} growth={}",
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

fi

if [ "$API" = "new" ]; then
cat > /tmp/poc_harness_final/src/main.rs <<'EOF'
fn main() {
    println!("{}", poc_harness_final::harness::run(1000));
}
EOF
else
cat > /tmp/poc_harness_final/src/main.rs <<'EOF'
fn main() {
    println!("{}", poc_harness_final::wit::harness::run(1000));
}
EOF
fi

cd /tmp/poc_harness_final
RUSTFLAGS='' cargo build --offline 2>&1 | tail -200
echo "---RUN---"
RUSTFLAGS='' ./target/debug/harness
