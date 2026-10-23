// Minimal harness: decode a raw JPEG2000 codestream via libavcodec directly,
// with AV_CODEC_FLAG_BITEXACT set, mirroring what the ffmpeg CLI's
// "-flags +bitexact" option (or the oss-fuzz target_dec_fuzzer harness under
// the right byte flags) would do. This exercises the real decoder entry
// points (avcodec_send_packet / avcodec_receive_frame) on the unmodified
// target source.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "libavcodec/avcodec.h"
#include "libavutil/frame.h"

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "usage: %s <input.j2k>\n", argv[0]);
        return 2;
    }
    FILE *f = fopen(argv[1], "rb");
    if (!f) { perror("fopen"); return 2; }
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    uint8_t *buf = av_malloc(sz + AV_INPUT_BUFFER_PADDING_SIZE);
    memset(buf, 0, sz + AV_INPUT_BUFFER_PADDING_SIZE);
    fread(buf, 1, sz, f);
    fclose(f);

    const AVCodec *codec = avcodec_find_decoder(AV_CODEC_ID_JPEG2000);
    if (!codec) { fprintf(stderr, "no jpeg2000 decoder\n"); return 2; }
    AVCodecContext *ctx = avcodec_alloc_context3(codec);
    ctx->flags |= AV_CODEC_FLAG_BITEXACT; // force FF_DWT97 -> FF_DWT97_INT path
    ctx->err_recognition = 0; // be lenient, like a fuzzer target would be
    int ret = avcodec_open2(ctx, codec, NULL);
    if (ret < 0) { fprintf(stderr, "open failed %d\n", ret); return 2; }

    AVPacket *pkt = av_packet_alloc();
    pkt->data = buf;
    pkt->size = sz;
    AVFrame *frame = av_frame_alloc();

    ret = avcodec_send_packet(ctx, pkt);
    fprintf(stderr, "send_packet ret=%d\n", ret);
    while (1) {
        ret = avcodec_receive_frame(ctx, frame);
        fprintf(stderr, "receive_frame ret=%d\n", ret);
        if (ret < 0) break;
        av_frame_unref(frame);
    }

    av_frame_free(&frame);
    av_packet_free(&pkt);
    avcodec_free_context(&ctx);
    av_free(buf);
    fprintf(stderr, "DONE\n");
    return 0;
}
