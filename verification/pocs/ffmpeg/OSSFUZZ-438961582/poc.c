#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <libavcodec/avcodec.h>
#include <libavutil/frame.h>

#define SENTINEL 0xAB

static int my_get_buffer2(AVCodecContext *avctx, AVFrame *frame, int flags) {
    int ret = avcodec_default_get_buffer2(avctx, frame, flags);
    if (ret < 0)
        return ret;
    for (int i = 0; i < AV_NUM_DATA_POINTERS; i++) {
        if (frame->buf[i])
            memset(frame->buf[i]->data, SENTINEL, frame->buf[i]->size);
    }
    return 0;
}

int main(int argc, char **argv) {
    if (argc < 4) {
        fprintf(stderr, "usage: %s width height infile [thread_count] [thread_type]\n", argv[0]);
        return 2;
    }
    int width = atoi(argv[1]);
    int height = atoi(argv[2]);
    const char *infile = argv[3];
    int thread_count = argc > 4 ? atoi(argv[4]) : 1;
    int thread_type = argc > 5 ? atoi(argv[5]) : 0;

    FILE *f = fopen(infile, "rb");
    if (!f) { perror("fopen"); return 2; }
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    uint8_t *buf = av_malloc(sz + AV_INPUT_BUFFER_PADDING_SIZE);
    fread(buf, 1, sz, f);
    fclose(f);

    const AVCodec *codec = avcodec_find_decoder(AV_CODEC_ID_DXV);
    if (!codec) { fprintf(stderr, "no dxv decoder\n"); return 2; }

    AVCodecContext *ctx = avcodec_alloc_context3(codec);
    ctx->width = width;
    ctx->height = height;
    ctx->thread_count = thread_count;
    ctx->thread_type = thread_type;
    ctx->get_buffer2 = my_get_buffer2;

    int ret = avcodec_open2(ctx, codec, NULL);
    if (ret < 0) {
        char errbuf[128];
        av_strerror(ret, errbuf, sizeof(errbuf));
        fprintf(stderr, "avcodec_open2 failed: %s\n", errbuf);
        return 3;
    }
    fprintf(stderr, "opened: coded_width=%d coded_height=%d active_thread_type=%d thread_count=%d\n",
            ctx->coded_width, ctx->coded_height, ctx->active_thread_type, ctx->thread_count);

    AVPacket *pkt = av_packet_alloc();
    pkt->data = buf;
    pkt->size = sz;

    AVFrame *frame = av_frame_alloc();
    ret = avcodec_send_packet(ctx, pkt);
    fprintf(stderr, "send_packet ret=%d\n", ret);
    if (ret >= 0) {
        ret = avcodec_receive_frame(ctx, frame);
        fprintf(stderr, "receive_frame ret=%d\n", ret);
        if (ret >= 0) {
            uint8_t b1 = frame->data[1] ? frame->data[1][0] : 0;
            uint8_t b2 = frame->data[2] ? frame->data[2][0] : 0;
            uint8_t b0 = frame->data[0] ? frame->data[0][0] : 0;
            fprintf(stderr, "plane0_byte0=0x%02x plane1_byte0=0x%02x plane2_byte0=0x%02x\n", b0, b1, b2);
            if (b1 == SENTINEL || b2 == SENTINEL) {
                fprintf(stderr, "BUG_OBSERVED: chroma plane untouched (sentinel 0x%02x survives) - decode succeeded without writing chroma data\n", SENTINEL);
            } else {
                fprintf(stderr, "CHROMA_WRITTEN: chroma plane bytes were overwritten by decoder\n");
            }
        }
    }

    av_frame_free(&frame);
    av_packet_free(&pkt);
    avcodec_free_context(&ctx);
    av_free(buf);
    fprintf(stderr, "DONE\n");
    return 0;
}
