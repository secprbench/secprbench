#include <libavcodec/avcodec.h>
#include <libavutil/frame.h>
#include <libavutil/imgutils.h>
#include <stdio.h>
#include <string.h>

int main(void) {
    const AVCodec *codec = avcodec_find_encoder(AV_CODEC_ID_DXV);
    if (!codec) { fprintf(stderr, "no codec\n"); return 1; }
    AVCodecContext *ctx = avcodec_alloc_context3(codec);
    ctx->width = 20;
    ctx->height = 16;
    ctx->pix_fmt = AV_PIX_FMT_RGBA;
    ctx->time_base = (AVRational){1, 25};
    if (avcodec_open2(ctx, codec, NULL) < 0) { fprintf(stderr, "open fail\n"); return 1; }

    AVFrame *frame = av_frame_alloc();
    frame->format = ctx->pix_fmt;
    frame->width = ctx->width;
    frame->height = ctx->height;
    /* align=32 forces frame->linesize[0] to include row padding beyond the
     * true pixel-row byte width (20*4=80 -> 96), which is required to expose
     * the uninitialized padding bytes in dxv_encode()'s safe_data buffer. */
    if (av_frame_get_buffer(frame, 32) < 0) { fprintf(stderr, "getbuf fail\n"); return 1; }
    fprintf(stderr, "linesize=%d width*4=%d\n", frame->linesize[0], ctx->width * 4);
    memset(frame->data[0], 0, (size_t)frame->linesize[0] * frame->height);

    AVPacket *pkt = av_packet_alloc();
    int ret = avcodec_send_frame(ctx, frame);
    if (ret < 0) { fprintf(stderr, "send fail %d\n", ret); return 1; }
    avcodec_send_frame(ctx, NULL);
    while (1) {
        ret = avcodec_receive_packet(ctx, pkt);
        if (ret == AVERROR(EAGAIN) || ret == AVERROR_EOF) break;
        if (ret < 0) { fprintf(stderr, "recv fail %d\n", ret); return 1; }
        fprintf(stderr, "got packet size=%d\n", pkt->size);
        av_packet_unref(pkt);
    }
    fprintf(stderr, "done\n");
    return 0;
}
