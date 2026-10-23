#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "libavcodec/avcodec.h"
#include "libavutil/log.h"

static unsigned char *read_file(const char *path, size_t *outlen) {
    FILE *f = fopen(path, "rb");
    if (!f) { perror(path); exit(1); }
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    unsigned char *buf = malloc(sz + 64);
    memset(buf, 0, sz + 64);
    fread(buf, 1, sz, f);
    fclose(f);
    *outlen = (size_t)sz;
    return buf;
}

int main(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr, "usage: %s extradata.bin frame.bin\n", argv[0]);
        return 1;
    }

    av_log_set_level(AV_LOG_DEBUG);

    const AVCodec *codec = avcodec_find_decoder(AV_CODEC_ID_AAC);
    if (!codec) { fprintf(stderr, "no aac decoder\n"); return 1; }

    AVCodecContext *ctx = avcodec_alloc_context3(codec);
    if (!ctx) { fprintf(stderr, "alloc ctx failed\n"); return 1; }

    size_t edlen;
    unsigned char *ed = read_file(argv[1], &edlen);
    ctx->extradata = av_mallocz(edlen + AV_INPUT_BUFFER_PADDING_SIZE);
    memcpy(ctx->extradata, ed, edlen);
    ctx->extradata_size = (int)edlen;

    int ret = avcodec_open2(ctx, codec, NULL);
    fprintf(stderr, "avcodec_open2 -> %d\n", ret);
    if (ret < 0) {
        char errbuf[256];
        av_strerror(ret, errbuf, sizeof(errbuf));
        fprintf(stderr, "open error: %s\n", errbuf);
        return 1;
    }

    fprintf(stderr, "opened: sample_rate=%d channels=%d object_type via profile=%d\n",
            ctx->sample_rate, ctx->ch_layout.nb_channels, ctx->profile);

    size_t flen;
    unsigned char *fr = read_file(argv[2], &flen);

    AVPacket *pkt = av_packet_alloc();
    pkt->data = fr;
    pkt->size = (int)flen;

    AVFrame *frame = av_frame_alloc();

    ret = avcodec_send_packet(ctx, pkt);
    fprintf(stderr, "send_packet -> %d\n", ret);

    ret = avcodec_receive_frame(ctx, frame);
    fprintf(stderr, "receive_frame -> %d\n", ret);

    av_frame_free(&frame);
    av_packet_free(&pkt);
    avcodec_free_context(&ctx);

    fprintf(stderr, "done\n");
    return 0;
}
