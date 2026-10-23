#include <libavformat/avformat.h>
#include <stdio.h>
#include <unistd.h>

int main(int argc, char **argv) {
    const char *path = argc > 1 ? argv[1] : "/poc/poc.ts";
    AVFormatContext *fmt = NULL;
    int ret = avformat_open_input(&fmt, path, NULL, NULL);
    if (ret < 0) {
        fprintf(stderr, "open_input failed: %d\n", ret);
        _exit(2);
    }
    AVPacket *pkt = av_packet_alloc();
    ret = av_read_frame(fmt, pkt);
    fprintf(stderr, "av_read_frame returned %d\n", ret);
    if (ret >= 0) {
        fprintf(stderr, "got packet size=%d\n", pkt->size);
        av_packet_unref(pkt);
    }
    fprintf(stderr, "PRE_CLOSE_OK\n");
    /* Intentionally skip avformat_close_input/av_packet_free to avoid
     * exercising unrelated cleanup-path code; we only care whether
     * reading the crafted packet itself caused an OOB write. */
    _exit(0);
}
