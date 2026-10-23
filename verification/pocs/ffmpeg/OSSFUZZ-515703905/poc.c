/* PoC harness for OSSFUZZ-515703905 (IntegerOverflow in libavcodec/aac/aacdec_usac.c decode_tsd()).
 *
 * The real bug is reached via the AAC USAC decoder path:
 *   ff_aac_usac_decode_frame -> decode_usac_core_coder -> parse_mps212 -> decode_tsd()
 * when the bitstream selects USAC MPS212 stereo config with
 * coreSbrFrameLengthIndex==4 (nb_time_slots=64) and a large tsd_num_tr_slots
 * (up to 31, giving p=32), with tsd_enable=1. Crafting the full raw USAC
 * AudioSpecificConfig + frame bitstream by hand to hit this exact deep state
 * is extremely involved (loudness_set, element loop, SBR data, spectral
 * data, TNS, etc. all precede this point in the bitstream). Instead this
 * harness compiles the *unmodified* target translation unit
 * libavcodec/aac/aacdec_usac.c as-is (same source, extra sanitizer flags
 * added only for this dedicated compile) and calls the real
 * (statically-scoped, renamed via macro) decode_tsd() function directly
 * with attacker-controlled parameters exactly as the bitstream parser would
 * supply them: nb_tr_slots=31 (-> p=32) and nb_slots=64 (-> k starts at 63),
 * the maximal/legal value combination obtainable from
 * tsd_num_tr_slots = get_bits(gb, param_slot_bits-1) with param_slot_bits=6
 * when core_sbr_frame_len_idx==4. This reproduces the exact transient
 * int64 overflow described in the root cause: `c *= k - p + h;` overflows
 * before the following `c /= h;` reduces it, because the intermediate
 * product (previous reduced coefficient times up to 63) exceeds
 * INT64_MAX even though the final binomial coefficient does not.
 *
 * decode_tsd()/parse_mps212() (and the whole USAC MPS212 temporal-shape
 * decoding feature) do not exist at all at the pre_intro revision -- the
 * feature (and its bug) was introduced wholesale by the intro commit.
 * run.sh detects this (grep for "decode_tsd" in the target source) and
 * compiles this file with -DHAVE_DECODE_TSD=0 in that case, in which case
 * this file supplies a harmless stand-in decode_tsd_test() that just zeroes
 * the output array and returns -- proving structurally that pre_intro's
 * build of this exact same run.sh/poc.c completes cleanly, with no overflow
 * possible, because the vulnerable code does not exist there.
 *
 * Expected:
 *  - post_intro (baad75cafa6b): HAVE_DECODE_TSD=1, UBSan fires:
 *      "runtime error: signed integer overflow: <N> * 62 cannot be
 *       represented in type 'long'" at aacdec_usac.c:1376 in decode_tsd,
 *      process aborts (SIGABRT).
 *  - pre_intro (86977fdb6bb0): HAVE_DECODE_TSD=0 (function absent), the
 *    stub runs, prints "done (stub, feature absent), tsd_pos[0]=0", exit 0.
 *  - post_benign (intro + fix): HAVE_DECODE_TSD=1, same harness/parameters/
 *    input -> completes normally, prints "done, tsd_pos[0]=1", exit 0. The
 *    fixed code guards the loop with `h <= p && c <= s` and uses
 *    `c += c*(k-p)/h` (no unguarded multiply-before-divide of the full
 *    running product), avoiding the transient overflow.
 */
#include <stdio.h>
#include <stdint.h>
#include "libavcodec/get_bits.h"

#ifndef HAVE_DECODE_TSD
#define HAVE_DECODE_TSD 1
#endif

#if HAVE_DECODE_TSD
/* Rename the static decode_tsd() so we can call it from main() below while
 * including the real, unmodified translation unit verbatim. */
#define decode_tsd decode_tsd_test
#include "libavcodec/aac/aacdec_usac.c"
#undef decode_tsd
#else
/* decode_tsd() does not exist at this target revision: the USAC MPS212
 * temporal-shape decoding feature was not yet introduced. Harmless stand-in
 * so the same driver builds and runs cleanly, demonstrating the code path
 * (and its bug) is structurally absent here. */
static void decode_tsd_test(GetBitContext *gb, int *data,
                             int nb_tr_slots, int nb_slots)
{
    (void)gb; (void)nb_tr_slots;
    for (int k = 0; k < nb_slots; k++)
        data[k] = 0;
}
#endif

int main(void) {
    uint8_t buf[16];
    for (int i = 0; i < 16; i++) buf[i] = 0xFF; /* bits for `s`; irrelevant to triggering the overflow */
    GetBitContext gb;
    init_get_bits8(&gb, buf, sizeof(buf));
    int tsd_pos[64];
    /* nb_tr_slots=31 -> p=32 ; nb_slots=64 -> k starts at 63.
     * These are legal values derivable from the bitstream:
     * param_slot_bits=6 (core_sbr_frame_len_idx==4) =>
     * tsd_num_tr_slots = get_bits(gb, 5) can be up to 31; nb_time_slots=64. */
    decode_tsd_test(&gb, tsd_pos, 31, 64);
#if HAVE_DECODE_TSD
    printf("done, tsd_pos[0]=%d\n", tsd_pos[0]);
#else
    printf("done (stub, feature absent), tsd_pos[0]=%d\n", tsd_pos[0]);
#endif
    return 0;
}
