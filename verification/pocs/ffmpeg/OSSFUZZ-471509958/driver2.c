#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "libavcodec/avcodec.h"

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: %s file\n", argv[0]); return 2; }

    const AVCodec *codec = avcodec_find_decoder_by_name("adpcm_ima_magix");
    if (!codec) {
        fprintf(stderr, "DECODER_NOT_FOUND\n");
        return 0;
    }

    FILE *f = fopen(argv[1], "rb");
    if (!f) { perror("fopen"); return 2; }
    fseek(f, 0, SEEK_END);
    long fsz = ftell(f);
    fseek(f, 0, SEEK_SET);
    /* Only the leading 68 bytes of our crafted file are the actual ADPCM
       packet; the trailing 1024 bytes are the fuzzer-harness parameter
       block and are not part of the real packet payload here. */
    long psz = fsz > 1024 ? fsz - 1024 : fsz;
    uint8_t *buf = av_malloc(psz + AV_INPUT_BUFFER_PADDING_SIZE);
    memset(buf, 0, psz + AV_INPUT_BUFFER_PADDING_SIZE);
    if (fread(buf, 1, psz, f) != (size_t)psz) { perror("fread"); return 2; }
    fclose(f);

    AVCodecContext *ctx = avcodec_alloc_context3(codec);
    ctx->sample_rate = 8000;
    av_channel_layout_default(&ctx->ch_layout, 1); /* mono, as in the crash */
    ctx->block_align = 1000000; /* far larger than the real packet, as in the crash */

    if (avcodec_open2(ctx, codec, NULL) < 0) {
        fprintf(stderr, "OPEN_FAILED\n");
        return 0;
    }

    AVPacket *pkt = av_packet_alloc();
    av_new_packet(pkt, psz);
    memcpy(pkt->data, buf, psz);

    int ret = avcodec_send_packet(ctx, pkt);
    fprintf(stderr, "send_packet ret=%d\n", ret);

    AVFrame *frame = av_frame_alloc();
    while (1) {
        ret = avcodec_receive_frame(ctx, frame);
        if (ret < 0)
            break;
        fprintf(stderr, "got frame nb_samples=%d\n", frame->nb_samples);
        av_frame_unref(frame);
    }

    fprintf(stderr, "DONE_NO_CRASH\n");
    return 0;
}
