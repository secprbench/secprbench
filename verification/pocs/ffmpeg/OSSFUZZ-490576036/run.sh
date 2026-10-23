#!/bin/bash
# Reproducer for OSSFUZZ-490576036 (extract_extradata LCEVC write_lcevc_nalu
# integer overflow -> heap-buffer-overflow READ).
#
# The ffmpeg_BSF_EXTRACT_EXTRADATA_fuzzer harness (tools/target_bsf_fuzzer.c)
# is not built as a standalone binary in this image, so this script compiles
# it on the fly (FFMPEG_BSF=extract_extradata) with a tiny main() that feeds
# $INPUT to LLVMFuzzerTestOneInput, against the already-built (sanitized)
# libavcodec/libavutil/etc static libraries under /work.
set -e
cd /work

cat > /tmp/driver.c << 'EOF'
#include <stdio.h>
#include <stdlib.h>
int LLVMFuzzerTestOneInput(const unsigned char *data, unsigned long size);
int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: %s file\n", argv[0]); return 1; }
    FILE *f = fopen(argv[1], "rb");
    if (!f) { perror("fopen"); return 1; }
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    unsigned char *buf = malloc(sz);
    fread(buf, 1, sz, f);
    fclose(f);
    LLVMFuzzerTestOneInput(buf, sz);
    printf("DONE_NO_CRASH\n");
    return 0;
}
EOF

clang -g -O1 -fsanitize=address -fno-omit-frame-pointer -DFFMPEG_BSF=extract_extradata \
  -I. -Ilibavutil -Ilibavcodec \
  tools/target_bsf_fuzzer.c /tmp/driver.c -o /tmp/bsf_fuzzer \
  libavcodec/libavcodec.a libavformat/libavformat.a libswresample/libswresample.a \
  libswscale/libswscale.a libavutil/libavutil.a -lm -lpthread -lz

INPUT="${1:-/poc/poc.bin}"
/tmp/bsf_fuzzer "$INPUT"
