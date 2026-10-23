/* Negative control: identical to harness_frame.c but bsOttBandsPhase=28
 * (== numBands, in-bounds) instead of 31. Expect NO crash even on
 * post_intro, isolating that the overflow is specifically caused by the
 * out-of-range value permitted by the missing bounds check. */
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
    BitWriter cw; memset(&cw, 0, sizeof(cw));
    bw_put(&cw, 0, 1); bw_put(&cw, 0, 1); bw_put(&cw, 0, 1);
    bw_put(&cw, 0, 4); bw_put(&cw, 0, 4);
    bw_put(&cw, 0, 1); bw_put(&cw, 0, 1);
    bw_put(&cw, 1, 2);
    bw_put(&cw, 1, 3);
    bw_put(&cw, 0, 3); bw_put(&cw, 0, 2); bw_put(&cw, 0, 2);
    bw_put(&cw, 0, 1);
    bw_put(&cw, 1, 1);
    bw_put(&cw, 1, 1);
    bw_put(&cw, 28, 5); /* bsOttBandsPhase = 28 (in-bounds, == numBands) */

    GetBitContext cgb;
    init_get_bits(&cgb, cw.buf, sizeof(cw.buf) * 8);

    AACDecContext ac; memset(&ac, 0, sizeof(ac));
    ac.avctx = NULL;

    AACUsacElemConfig e; memset(&e, 0, sizeof(e));
    e.sbr.ratio = 1;

    int cret = decode_usac_element_pair(&ac, &e, &cgb);
    printf("CONFIG ret=%d otts_bands_phase=%d\n", cret, e.mps.otts_bands_phase);
    if (cret < 0) { printf("RESULT rejected at config stage\n"); return 0; }

    BitWriter fw; memset(&fw, 0, sizeof(fw));
    bw_put(&fw, 0, 1);
    bw_put(&fw, 0, 2); bw_put(&fw, 0, 2);
    bw_put(&fw, 0, 2); bw_put(&fw, 0, 2);
    bw_put(&fw, 1, 1); bw_put(&fw, 0, 1);
    bw_put(&fw, 3, 2); bw_put(&fw, 0, 2);
    bw_put(&fw, 0, 1); bw_put(&fw, 0, 1); bw_put(&fw, 3, 2);
    bw_put(&fw, 0, 1); bw_put(&fw, 1, 1); bw_put(&fw, 0, 1);
    for (int i = 0; i < 31; i++) bw_put(&fw, 0, 1);

    GetBitContext fgb;
    init_get_bits(&fgb, fw.buf, sizeof(fw.buf) * 8);

    AACUSACConfig usac; memset(&usac, 0, sizeof(usac));
    AACUsacMPSData mps; memset(&mps, 0, sizeof(mps));

    int fret = parse_mps212(&ac, &usac, &mps, &e, &fgb, 0);
    printf("RESULT parse_mps212 ret=%d (no crash expected with in-bounds value)\n", fret);
    return 0;
}
