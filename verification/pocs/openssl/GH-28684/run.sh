#!/bin/sh
# Builds and runs the alignment-dispatch harness against the real
# crypto/chacha/chacha_riscv.c from the target tree being tested.
set -e
BUILD=$(mktemp -d)
cp /work/crypto/chacha/chacha_riscv.c "$BUILD/"
cp /poc/stub.c "$BUILD/"
cd "$BUILD"
clang -O0 -g -I/work/include -w -c chacha_riscv.c -o chacha_riscv.o
clang -O0 -g -I/work/include -w -c stub.c -o stub.o
clang chacha_riscv.o stub.o -o poc
./poc
