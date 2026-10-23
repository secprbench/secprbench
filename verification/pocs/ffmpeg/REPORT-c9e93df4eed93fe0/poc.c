#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <libavcodec/avcodec.h>
#include <libavutil/frame.h>

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: %s file\n", argv[0]); return 1; }
    FILE *f = fopen(argv[1], "rb");
    if (!f) { perror("fopen"); return 1; }
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    uint8_t *buf = av_malloc(sz + AV_INPUT_BUFFER_PADDING_SIZE);
    memset(buf, 0, sz + AV_INPUT_BUFFER_PADDING_SIZE);
    fread(buf, 1, sz, f);
    fclose(f);

    const AVCodec *codec = avcodec_find_decoder(AV_CODEC_ID_PRORES_RAW);
    if (!codec) {
        /* Expected on revisions that predate the prores_raw decoder: the
         * codepath under test does not exist yet, so there is nothing to
         * exercise. This is not a harness failure. */
        fprintf(stderr, "no decoder (codepath not present on this revision)\n");
        return 0;
    }
    AVCodecContext *ctx = avcodec_alloc_context3(codec);
    if (!ctx) { fprintf(stderr, "no ctx\n"); return 1; }

    if (avcodec_open2(ctx, codec, NULL) < 0) {
        fprintf(stderr, "open failed\n");
        return 1;
    }

    AVPacket *pkt = av_packet_alloc();
    av_packet_from_data(pkt, buf, sz);

    AVFrame *frame = av_frame_alloc();

    int ret = avcodec_send_packet(ctx, pkt);
    fprintf(stderr, "send_packet ret=%d\n", ret);
    if (ret >= 0) {
        ret = avcodec_receive_frame(ctx, frame);
        fprintf(stderr, "receive_frame ret=%d w=%d h=%d coded_w=%d coded_h=%d\n",
                ret, ctx->width, ctx->height, ctx->coded_width, ctx->coded_height);
    }

    av_frame_free(&frame);
    av_packet_free(&pkt);
    avcodec_free_context(&ctx);
    fprintf(stderr, "DONE\n");
    return 0;
}
