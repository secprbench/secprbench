// Same white-box harness as harness.c, but for the pre_intro revision where
// dequantization_int_97() had a different signature (no M_b parameter) and
// a different (safe, 64-bit) implementation. Included verbatim, unmodified.
#include <stdio.h>
#include <stdint.h>
#include <string.h>

#include "libavcodec/jpeg2000dec.c"

int main(void) {
    Jpeg2000Cblk cblk;
    Jpeg2000Component comp;
    Jpeg2000T1Context t1;
    Jpeg2000Band band;
    int32_t out_buf[4];
    memset(&cblk, 0, sizeof(cblk));
    memset(&comp, 0, sizeof(comp));
    memset(&t1, 0, sizeof(t1));
    memset(&band, 0, sizeof(band));
    memset(out_buf, 0, sizeof(out_buf));

    cblk.coord[0][0] = 0; cblk.coord[0][1] = 1; // w = 1
    cblk.coord[1][0] = 0; cblk.coord[1][1] = 1; // h = 1

    comp.coord[0][0] = 0; comp.coord[0][1] = 1;
    comp.i_data = out_buf;

    t1.stride = 4;
    // Same coefficient value as in the post_intro harness.
    t1.data[0] = 2147483640;

    band.i_stepsize = 128; // matches the scale computed internally in post_intro's harness run

    dequantization_int_97(0, 0, &cblk, &comp, &t1, &band);

    printf("HARNESS_DONE out=%d i_stepsize=%d\n", out_buf[0], band.i_stepsize);
    return 0;
}
