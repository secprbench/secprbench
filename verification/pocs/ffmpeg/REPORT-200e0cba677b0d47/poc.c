#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <libavfilter/avfilter.h>
#include <libavfilter/buffersrc.h>
#include <libavfilter/buffersink.h>
#include <libavutil/opt.h>
#include <libavutil/frame.h>
#include <libavutil/imgutils.h>

int main(void)
{
    const AVFilter *estdif = avfilter_get_by_name("estdif");
    if (!estdif) {
        printf("SKIP: estdif filter not present in this build\n");
        return 0;
    }

    int width = 2, height = 2000000;
    enum AVPixelFormat fmt = AV_PIX_FMT_YUV420P;

    AVFilterGraph *graph = avfilter_graph_alloc();
    if (!graph) { fprintf(stderr, "FAIL: alloc graph\n"); return 2; }
    graph->nb_threads = 1500;

    const AVFilter *buffersrc = avfilter_get_by_name("buffer");
    const AVFilter *buffersink = avfilter_get_by_name("buffersink");
    if (!buffersrc || !buffersink) { fprintf(stderr, "FAIL: missing buffer/buffersink\n"); return 2; }

    char args[256];
    snprintf(args, sizeof(args),
             "video_size=%dx%d:pix_fmt=%d:time_base=1/25:pixel_aspect=1/1",
             width, height, (int)fmt);

    AVFilterContext *src_ctx = NULL, *estdif_ctx = NULL, *sink_ctx = NULL;
    int ret;

    ret = avfilter_graph_create_filter(&src_ctx, buffersrc, "in", args, NULL, graph);
    if (ret < 0) { fprintf(stderr, "FAIL: create src ret=%d\n", ret); return 2; }

    ret = avfilter_graph_create_filter(&estdif_ctx, estdif, "estdif", NULL, NULL, graph);
    if (ret < 0) { fprintf(stderr, "FAIL: create estdif ret=%d\n", ret); return 2; }

    ret = avfilter_graph_create_filter(&sink_ctx, buffersink, "out", NULL, NULL, graph);
    if (ret < 0) { fprintf(stderr, "FAIL: create sink ret=%d\n", ret); return 2; }

    ret = avfilter_link(src_ctx, 0, estdif_ctx, 0);
    if (ret < 0) { fprintf(stderr, "FAIL: link1 ret=%d\n", ret); return 2; }
    ret = avfilter_link(estdif_ctx, 0, sink_ctx, 0);
    if (ret < 0) { fprintf(stderr, "FAIL: link2 ret=%d\n", ret); return 2; }

    ret = avfilter_graph_config(graph, NULL);
    if (ret < 0) { fprintf(stderr, "FAIL: config ret=%d\n", ret); return 2; }

    for (int i = 0; i < 3; i++) {
        AVFrame *frame = av_frame_alloc();
        frame->format = fmt;
        frame->width = width;
        frame->height = height;
        ret = av_frame_get_buffer(frame, 32);
        if (ret < 0) { fprintf(stderr, "FAIL: get_buffer ret=%d\n", ret); return 2; }
        memset(frame->data[0], 0, (size_t)frame->linesize[0] * height);
        memset(frame->data[1], 0, (size_t)frame->linesize[1] * ((height + 1) / 2));
        memset(frame->data[2], 0, (size_t)frame->linesize[2] * ((height + 1) / 2));
        frame->pts = i;

        ret = av_buffersrc_add_frame(src_ctx, frame);
        av_frame_free(&frame);
        if (ret < 0) { fprintf(stderr, "FAIL: add_frame[%d] ret=%d\n", i, ret); return 2; }

        AVFrame *out = av_frame_alloc();
        ret = av_buffersink_get_frame(sink_ctx, out);
        if (ret < 0)
            fprintf(stderr, "INFO: get_frame[%d] ret=%d\n", i, ret);
        else
            printf("OK: got output frame[%d] %dx%d\n", i, out->width, out->height);
        av_frame_free(&out);
    }

    ret = av_buffersrc_add_frame(src_ctx, NULL);
    if (ret < 0) fprintf(stderr, "INFO: eof add_frame ret=%d\n", ret);

    for (int i = 0; i < 3; i++) {
        AVFrame *out = av_frame_alloc();
        ret = av_buffersink_get_frame(sink_ctx, out);
        if (ret < 0) {
            fprintf(stderr, "INFO: flush get_frame[%d] ret=%d\n", i, ret);
            av_frame_free(&out);
            break;
        } else {
            printf("OK: flush output frame[%d] %dx%d\n", i, out->width, out->height);
        }
        av_frame_free(&out);
    }

    avfilter_graph_free(&graph);
    printf("DONE\n");
    return 0;
}
