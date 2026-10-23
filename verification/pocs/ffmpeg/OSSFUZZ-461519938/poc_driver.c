/*
 * Direct-call PoC for OSSFUZZ-461519938 (libswscale/output.c,
 * yuv2gbrp16_full_X_c): the Y + R / Y + G / Y + B additions are done in
 * plain 32-bit signed int and can overflow.
 *
 * This translation unit #includes libswscale/output.c so it can call the
 * (static) yuv2gbrp16_full_X_c() directly with crafted filter taps and
 * coefficients that reproduce the exact class of overflow from the
 * OSS-Fuzz report:
 *   "signed integer overflow: -1159988356 + -1082982400 cannot be
 *    represented in type 'int'"
 *
 * We drive the internal accumulators to known, deliberately chosen values:
 *   - lumFilterSize = 0  => Y collapses to the fixed bias term added after
 *     scaling. In the *introduced* (buggy) code this bias is
 *     (1<<13)-(1<<29) = -536862720. In the pre-bug code the bias is only
 *     (1<<13) and an intermediate av_clip_uintp2(Y+R, 30) clamps the sum
 *     before it can leave the 32-bit range, and the fixed benign fix widens
 *     the Y+R addition to 64-bit.
 *   - chrFilterSize = 1 with a single tap of weight 1 lets us set V (and
 *     hence R = V * yuv2rgb_v2r_coeff) to an exact, large negative value
 *     that by itself fits in an int, but whose sum with the biased Y does
 *     not.
 *
 * No source file is modified; this file is added under /poc only.
 */

#include <stdint.h>
#include <string.h>
#include <stdio.h>

#define HAVE_AV_CONFIG_H 1
#define BUILDING_swscale 1

#include "libswscale/output.c"

int main(void)
{
    struct SwsContext c;
    memset(&c, 0, sizeof(c));

    c.dstFormat = AV_PIX_FMT_GBRP16LE; /* no alpha, so hasAlpha == 0 */

    c.yuv2rgb_y_offset   = 0;
    c.yuv2rgb_y_coeff    = 1;
    c.yuv2rgb_v2r_coeff  = 100000;
    c.yuv2rgb_v2g_coeff  = 0;
    c.yuv2rgb_u2g_coeff  = 0;
    c.yuv2rgb_u2b_coeff  = 0;

    /* Chosen so that, after the ">>14" shift, V == -20000 exactly:
     *   V_pre = -(128<<23) + chrVSrc[0]*chrFilter[0]
     *         = -1073741824 + 746061824 = -327680000
     *   V = V_pre >> 14 = -20000
     *   R = V * yuv2rgb_v2r_coeff = -20000 * 100000 = -2000000000
     * (R itself fits comfortably in a 32-bit int -- no UB in the
     * multiplication.)
     */
    int32_t lumRow[1]  = { 0 };
    int32_t chrURow[1] = { 0 };
    int32_t chrVRow[1] = { 746061824 };

    const int16_t *lumSrc[1]  = { (const int16_t *)lumRow };
    const int16_t *chrUSrc[1] = { (const int16_t *)chrURow };
    const int16_t *chrVSrc[1] = { (const int16_t *)chrVRow };

    int16_t lumFilter[1] = { 0 }; /* unused: lumFilterSize == 0 */
    int16_t chrFilter[1] = { 1 };

    uint16_t rowG[1] = { 0 }, rowB[1] = { 0 }, rowR[1] = { 0 };
    uint8_t *dest[4];
    dest[0] = (uint8_t *)rowG;
    dest[1] = (uint8_t *)rowB;
    dest[2] = (uint8_t *)rowR;
    dest[3] = NULL;

    fprintf(stderr, "poc: calling yuv2gbrp16_full_X_c with Y-bias and "
                     "R chosen so Y + R overflows a 32-bit int...\n");

    yuv2gbrp16_full_X_c(&c, lumFilter, lumSrc, 0,
                        chrFilter, chrUSrc, chrVSrc, 1,
                        NULL, dest, 1, 0);

    fprintf(stderr, "poc: no overflow detected. rowR[0]=%u rowG[0]=%u "
                     "rowB[0]=%u\n", rowR[0], rowG[0], rowB[0]);
    return 0;
}
