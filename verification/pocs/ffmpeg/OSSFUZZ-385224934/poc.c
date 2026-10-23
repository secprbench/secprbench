#include <stdio.h>
#include <libavformat/avformat.h>

int main(int argc, char **argv) {
    av_log_set_level(AV_LOG_ERROR);
    AVFormatContext *fmt = NULL;
    const char *path = argc > 1 ? argv[1] : "/poc/poc2.w64";
    int ret = avformat_open_input(&fmt, path, NULL, NULL);
    if (ret < 0) {
        char buf[128];
        av_strerror(ret, buf, sizeof(buf));
        printf("OPEN_FAILED: %s\n", buf);
        return 1;
    }
    for (unsigned i = 0; i < fmt->nb_streams; i++) {
        AVCodecParameters *par = fmt->streams[i]->codecpar;
        printf("STREAM %u: block_align=%d channels=%d bits_per_coded_sample=%d bit_rate=%lld\n",
               i, par->block_align, par->ch_layout.nb_channels,
               par->bits_per_coded_sample, (long long)par->bit_rate);
    }
    avformat_close_input(&fmt);
    return 0;
}
