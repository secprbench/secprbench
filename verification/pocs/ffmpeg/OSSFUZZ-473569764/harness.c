// White-box unit harness: directly exercises the real, unmodified
// dequantization_int_97() from libavcodec/jpeg2000dec.c (the function named
// in this task's root_cause) by #including the target source file verbatim
// (no edits to the tracked source) and calling it with a coefficient
// magnitude matching the one named in the upstream fix commit message
// ("signed integer overflow: 2147483640 + 32 cannot be represented in type
// 'int'"). This is compiled with -fsanitize=signed-integer-overflow so the
// exact defective addition traps under UBSan.
#include <stdio.h>
#include <stdint.h>

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

    // A single-coefficient 1x1 code-block.
    cblk.coord[0][0] = 0; cblk.coord[0][1] = 1; // w = 1
    cblk.coord[1][0] = 0; cblk.coord[1][1] = 1; // h = 1

    comp.coord[0][0] = 0; comp.coord[0][1] = 1;
    comp.i_data = out_buf;

    t1.stride = 4;
    // Sign-magnitude encoded coefficient: sign flag (bit31) clear, magnitude
    // 2147483640 in the low 31 bits -- exactly the value named in the fix's
    // "Fixes:" line for the UBSan report this task is about.
    t1.data[0] = 2147483640;

    band.f_stepsize = 1.0f;

    int M_b = 8; // plausible magnitude-bits value; irrelevant to the overflow

    dequantization_int_97(0, 0, &cblk, &comp, &t1, &band, M_b);

    printf("HARNESS_DONE out=%d i_stepsize=%d\n", out_buf[0], band.i_stepsize);
    return 0;
}
