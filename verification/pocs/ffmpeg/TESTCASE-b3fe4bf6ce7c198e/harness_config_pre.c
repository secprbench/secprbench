/* Same as harness_config.c, but without referencing struct fields that were
 * only added by the introducing commit (otts_bands_phase_present). Used to
 * show that, pre-intro, the exact same crafted bits are parsed by the exact
 * same decode_usac_element_pair() field order (freq_res, ..., phase_coding,
 * bsOttBandsPhasePresent(inline)/bsOttBandsPhase) with no validation either
 * -- but pre-intro there is no parse_mps212()/consumer at all, so the value
 * is stored and never used to size any array (confirmed by source
 * inspection: no aacdec_usac_mps212.* and no parse_mps212 references).
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

    bw_put(&bw, 0, 1); bw_put(&bw, 0, 1); bw_put(&bw, 0, 1);
    bw_put(&bw, 0, 4); bw_put(&bw, 0, 4);
    bw_put(&bw, 0, 1); bw_put(&bw, 0, 1);

    bw_put(&bw, 1, 2); /* stereo_config_index = 1 */
    bw_put(&bw, 1, 3); /* bsFreqRes = 1 */
    bw_put(&bw, 0, 3); bw_put(&bw, 0, 2); bw_put(&bw, 0, 2);
    bw_put(&bw, 0, 1); /* bsHighRateMode */
    bw_put(&bw, 1, 1); /* bsPhaseCoding = 1 */
    bw_put(&bw, 1, 1); /* bsOttBandsPhasePresent = 1 */
    bw_put(&bw, 31, 5); /* bsOttBandsPhase = 31 */

    GetBitContext gb;
    init_get_bits(&gb, bw.buf, sizeof(bw.buf) * 8);

    AACDecContext ac; memset(&ac, 0, sizeof(ac));
    ac.avctx = NULL;

    AACUsacElemConfig e; memset(&e, 0, sizeof(e));
    e.sbr.ratio = 1;

    int ret = decode_usac_element_pair(&ac, &e, &gb);

    printf("RESULT ret=%d freq_res=%d otts_bands_phase=%d "
           "phase_coding=%d residual_coding=%d stereo_config_index=%d\n",
           ret, e.mps.freq_res, e.mps.otts_bands_phase,
           e.mps.phase_coding, e.mps.residual_coding, e.stereo_config_index);

    return 0;
}
