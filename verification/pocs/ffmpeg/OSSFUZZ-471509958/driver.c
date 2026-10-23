#include <stdio.h>
#include <stdlib.h>
#include "libavcodec/codec_internal.h"

const FFCodec * codec_list[3] = { NULL, NULL, NULL };

extern int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size);

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: %s file\n", argv[0]); return 1; }
    FILE *f = fopen(argv[1], "rb");
    if (!f) { perror("fopen"); return 1; }
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    unsigned char *buf = malloc(sz + 64);
    if (fread(buf, 1, sz, f) != (size_t)sz) { perror("fread"); return 1; }
    fclose(f);
    LLVMFuzzerTestOneInput(buf, sz);
    fprintf(stderr, "DONE_NO_CRASH\n");
    return 0;
}
