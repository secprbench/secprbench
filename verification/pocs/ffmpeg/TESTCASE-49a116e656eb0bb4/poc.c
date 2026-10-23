#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

#if defined(__has_include)
#  if __has_include("libavcodec/aac/aacdec_usac_mps212.h")
#    define HAVE_MPS212 1
#  endif
#endif

#ifdef HAVE_MPS212
#include "libavcodec/aac/aacdec_usac_mps212.h"
#include "libavcodec/get_bits.h"
#endif

int main(void) {
#ifndef HAVE_MPS212
    /* This revision does not contain the USAC MPS212 lossless-data decoder
       (libavcodec/aac/aacdec_usac_mps212.{c,h}) at all -- the feature and
       its ff_aac_ec_data_dec()/ec_pair_dec()/attach_lsb() code path were
       introduced by a later commit, so there is nothing to exercise here. */
    printf("MPS212 decoder not present in this revision; nothing to test\n");
    return 0;
#else
    int size = 4096;
    uint8_t *buf = calloc(1, size + 64);

    /* Control bits, MSB-first, packed starting at bit offset 0.
       pos, nbits, value */
    struct { int pos; int nbits; unsigned val; } ctrl[] = {
        {0,  2, 3},  /* data_mode[0] = 3 (EC_DATA) */
        {2,  1, 1},  /* data_pair (pair) = 1 */
        {3,  1, 0},  /* coarse_quant = 0 */
        {4,  2, 3},  /* freq_res = 3 -> stride 28 */
        {6,  1, 0},  /* pcm_coding = 0 */
        {7,  1, 0},  /* diff_freq[0] bit -> diff_freq[0] = !0 = 1 */
        {8,  1, 0},  /* diff_freq[1] bit -> diff_freq[1] = !0 = 1 */
        {9,  1, 1},  /* dim = 1 (2D) */
        {10, 1, 1},  /* time_pair = 1 */
        {11, 1, 0},  /* huff_data_2d lav_idx first branch bit -> lav=3 */
    };
    for (int c = 0; c < (int)(sizeof(ctrl)/sizeof(ctrl[0])); c++) {
        int pos = ctrl[c].pos, n = ctrl[c].nbits;
        unsigned v = ctrl[c].val;
        for (int b = 0; b < n; b++) {
            int bitpos = pos + b;
            int byte = bitpos / 8, bit = 7 - (bitpos % 8);
            unsigned bitval = (v >> (n - 1 - b)) & 1;
            if (bitval)
                buf[byte] |= (1 << bit);
        }
    }

    GetBitContext gb;
    if (init_get_bits8(&gb, buf, size) < 0) {
        fprintf(stderr, "init_get_bits8 failed\n");
        return 1;
    }

    AACMPSLosslessData ld;
    memset(&ld, 0, sizeof(ld));

    /* start_band=0, end_band=28 (=> nb_bands=28=MPS_MAX_PARAM_BANDS),
       frame_indep_flag=0, indep_flag=0, nb_param_sets=1 */
    int err = ff_aac_ec_data_dec(&gb, &ld, MPS_CLD, 0,
                                  0, 28, 0, 0, 1);
    printf("ff_aac_ec_data_dec returned %d\n", err);
    free(buf);
    return 0;
#endif
}
