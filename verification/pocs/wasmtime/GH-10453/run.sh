#!/bin/bash
set -e
mkdir -p /tmp/pocbuild_run /tmp/pocsrc_run
cp /poc/Cargo.toml /poc/main.rs /tmp/pocsrc_run/
cd /tmp/pocsrc_run
unset RUSTFLAGS
export CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_RUSTFLAGS="-Zsanitizer=address -Cforce-frame-pointers=yes"
cargo build --release --offline --target x86_64-unknown-linux-gnu --target-dir /tmp/pocbuild_run 2>&1 | tail -40
echo ===RUN===
RUST_LOG=wasmtime::runtime::vm::gc=trace /tmp/pocbuild_run/x86_64-unknown-linux-gnu/release/poc
echo "EXIT=$?"
