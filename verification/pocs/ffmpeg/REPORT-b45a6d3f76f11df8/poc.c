#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include "libavcodec/avcodec.h"
#include "libavutil/channel_layout.h"
#include "libavutil/mem.h"

int main(void) {
    const AVCodec *codec = avcodec_find_decoder(AV_CODEC_ID_ADPCM_N64);
    if (!codec) {
        printf("RESULT:NO_DECODER\n");
        return 0;
    }

    AVCodecContext *ctx = avcodec_alloc_context3(codec);
    if (!ctx) { printf("RESULT:ALLOC_FAIL\n"); return 1; }

    av_channel_layout_default(&ctx->ch_layout, 1);
    ctx->sample_rate = 32000;

    /* Craft extradata: version=1, order=2, entries=8, then order*entries*8=128
     * be16 coefficients. Only coefs[8] (the coefficient multiplied against
     * sf_codes[0] when reconstructing sample index 1, k=0) is set to the
     * max positive int16 (0x7FFF); every other coefficient is 0, so that
     * exactly ONE multiplication in the predictor ('sf_codes[(i-1)-k] *
     * coefs[(o*8)+k]') can become large - isolating the single vulnerable
     * expression instead of cascading into unrelated overflows. */
    int version = 1, order = 2, entries = 8;
    int ncoefs = order * entries * 8;
    int extra_size = 6 + ncoefs * 2;
    uint8_t *extradata = av_mallocz(extra_size + AV_INPUT_BUFFER_PADDING_SIZE);
    int p = 0;
    extradata[p++] = (version >> 8) & 0xff; extradata[p++] = version & 0xff;
    extradata[p++] = (order >> 8) & 0xff;   extradata[p++] = order & 0xff;
    extradata[p++] = (entries >> 8) & 0xff; extradata[p++] = entries & 0xff;
    for (int i = 0; i < ncoefs; i++) {
        if (i == 8) { extradata[p++] = 0x7f; extradata[p++] = 0xff; }
        else        { extradata[p++] = 0x00; extradata[p++] = 0x00; }
    }
    ctx->extradata = extradata;
    ctx->extradata_size = extra_size;

    if (avcodec_open2(ctx, codec, NULL) < 0) {
        printf("RESULT:OPEN_FAIL\n");
        return 0;
    }

    /* One 9-byte ADPCM_N64 block:
     * byte0: high nibble = scale exponent (0xF -> scale = 1<<15 = 32768),
     *        low nibble = index (unused by the overflow path).
     * byte1: high nibble 0x7 -> codes[0] = 7 * 32768 = 229376 (sf_codes[0]
     *        for j=0); low nibble 0 -> codes[1] = 0.
     * bytes2..8: all-zero nibbles -> every other code is 0.
     * With only coefs[8] and codes[0] non-zero, the single product
     * sf_codes[0] * coefs[8] (used to reconstruct sample index 1) is the
     * only term that can overflow a 32-bit int: 229376 * 32767 =
     * 7515963392, which exceeds INT_MAX (2147483647). */
    uint8_t block[9] = {0xF0, 0x70, 0, 0, 0, 0, 0, 0, 0};

    AVPacket *pkt = av_packet_alloc();
    av_new_packet(pkt, 9);
    memcpy(pkt->data, block, 9);

    AVFrame *frame = av_frame_alloc();

    int ret = avcodec_send_packet(ctx, pkt);
    if (ret < 0) { printf("RESULT:SEND_FAIL:%d\n", ret); return 0; }

    ret = avcodec_receive_frame(ctx, frame);
    if (ret < 0) { printf("RESULT:RECV_FAIL:%d\n", ret); return 0; }

    int16_t *out = (int16_t *)frame->extended_data[0];
    printf("RESULT:SAMPLES:");
    for (int i = 0; i < frame->nb_samples; i++)
        printf("%d,", out[i]);
    printf("\n");

    /* Mathematically-correct (non-overflowing) value for sample index 1,
     * using the exact same coefficients/codes but wide (64-bit) arithmetic
     * mirroring the decoder's algorithm for j=0, i=1. */
    int64_t coef8 = 0x7fff;
    int64_t codes0 = 229376; /* sf_codes[0] */
    int64_t codes1 = 0;      /* sf_codes[1] */
    int64_t delta64 = codes0 * coef8; /* the single k=0 term; order-loop
                                          term is 0 because hist is 0 for
                                          block 0, all other k-loop terms
                                          are 0 because codes/coefs are 0 */
    int64_t sample64 = codes1 * 2048;
    sample64 = (sample64 + delta64) / 2048;
    int expected;
    if (sample64 > 32767) expected = 32767;
    else if (sample64 < -32768) expected = -32768;
    else expected = (int)sample64;

    printf("RESULT:EXPECTED_I1:%d ACTUAL_I1:%d\n", expected, out[1]);
    printf("RESULT:MATCH:%d\n", expected == out[1]);

    return 0;
}
