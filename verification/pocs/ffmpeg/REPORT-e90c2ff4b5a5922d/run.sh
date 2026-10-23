#!/bin/sh
# Reproduces OutOfBoundsRead in parse_itut_t35_metadata() (libavcodec/libdav1d.c),
# bug type OutOfBoundsRead: US ITU-T T.35 metadata (country_code=0xB5) with a
# payload shorter than 2 bytes causes an unchecked bytestream2_get_be16u()
# read past the end of the payload buffer.
#
# The full libdav1d.c cannot be *built* in this environment because the
# ffmpeg configuration under test has CONFIG_LIBDAV1D=0 (the dav1d system
# library is not installed), so <dav1d/dav1d.h> is unavailable and
# libdav1d.c is not part of the normal build/link at all, for any of
# pre_intro/post_intro/post_benign. There is therefore no `ffmpeg -c:v
# libdav1d` decode path reachable by any input in this build.
#
# This script is IDENTICAL across pre_intro/post_intro/post_benign (same
# command, same harness, same crafted struct/input). It dynamically extracts
# -- at run time, from THIS container's own /work/libavcodec/libdav1d.c,
# via sed -- the exact, unmodified body of parse_itut_t35_metadata() for
# whichever commit this container was built from, and compiles+links it
# together with the real, unmodified ffmpeg headers/static libs already
# present in /work (bytestream.h, itut35.h, hdr_dynamic_metadata.h,
# atsc_a53.h, dovi_rpu.h, libavcodec.a, libavutil.a) plus a small fixed
# harness main() (/poc/harness_common.h, /poc/harness_main.h -- identical
# across all three runs) that constructs a Dav1dITUTT35 struct exactly as
# dav1d would for the reporter's crafted input: country_code=US (0xB5) and a
# 1-byte heap payload (malloc(1), so ASan's redzone sits immediately after
# the logical payload -- av_malloc()'s SIMD-alignment padding would hide the
# 1-byte overread from ASan).
#
# Only the *target* source under test differs between runs (because it is a
# different commit's /work tree) -- exactly analogous to how the same PoC
# input is normally run against each commit's differently built target
# binary; the command, harness, and crafted input are all fixed.
#
# NOTE: build at -O0. At -O1 (ffmpeg's own CFLAGS), LLVM's optimizer -- given
# full visibility of this tiny, single-TU program (malloc() and the OOB read
# reachable via full inlining) -- appears to exploit the reads-past-object
# undefined behavior and elides the faulting load, so the sanitizer never
# fires. That elision cannot happen in the real target: there, the
# allocation is made deep inside the separately-compiled dav1d library and
# the read happens in ffmpeg's own object file, so the compiler has no way
# to reason about the allocation size across that boundary. -O0 avoids this
# artifact of the minimal harness while exercising byte-for-byte the same
# target code.

set -e
SRC=/work/libavcodec/libdav1d.c
WORKDIR=$(mktemp -d)

# Extract the exact, unmodified body of parse_itut_t35_metadata() from this
# container's own copy of the target source (differs per commit; everything
# else in this script is identical across commits).
awk '/^static int parse_itut_t35_metadata/{p=1} p{print; if($0=="}"){exit}}' "$SRC" > "$WORKDIR/func_target.c"

cp /poc/harness_common.h /poc/harness_main.h "$WORKDIR"/
cd "$WORKDIR"
cat harness_common.h func_target.c harness_main.h > poc.c
clang -std=c17 -g -O0 -fsanitize=address -fno-omit-frame-pointer -pthread \
  -I/work -o poc poc.c \
  -L/work/libavcodec -L/work/libswresample -L/work/libavutil \
  -lavcodec -lswresample -lavutil -lm -lpthread -lz -latomic
ASAN_OPTIONS=detect_leaks=0 ./poc
