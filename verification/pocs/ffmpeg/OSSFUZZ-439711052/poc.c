#include <stdio.h>
#include <string.h>
#include "libavcodec/hevc/sei.h"
#include "libavcodec/get_bits.h"

int main(int argc, char **argv) {
    FILE *f = fopen(argv[1], "rb");
    if (!f) { perror("fopen"); return 1; }
    uint8_t buf[4096];
    int n = fread(buf, 1, sizeof(buf), f);
    fclose(f);
    fprintf(stderr, "read %d bytes\n", n);

    HEVCSEI sei;
    memset(&sei, 0, sizeof(sei));

    GetBitContext gb;
    if (init_get_bits8(&gb, buf, n) < 0) {
        fprintf(stderr, "init_get_bits8 failed\n");
        return 1;
    }

    int ret = ff_hevc_decode_nal_sei(&gb, NULL, &sei, NULL, HEVC_NAL_SEI_PREFIX);
    fprintf(stderr, "ff_hevc_decode_nal_sei returned %d\n", ret);
    return 0;
}
