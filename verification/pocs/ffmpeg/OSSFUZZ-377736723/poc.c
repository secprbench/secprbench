#include <stdio.h>
#include <libavformat/avformat.h>

int main(int argc, char **argv) {
    const char *path = argc > 1 ? argv[1] : "/tmp/poc.mov";
    av_log_set_level(AV_LOG_ERROR);
    AVFormatContext *fmt = NULL;
    int ret = avformat_open_input(&fmt, path, NULL, NULL);
    if (ret < 0) {
        char buf[128];
        av_strerror(ret, buf, sizeof(buf));
        printf("OPEN_FAILED: %s\n", buf);
        return 1;
    }
    for (unsigned i = 0; i < fmt->nb_streams; i++) {
        AVStream *st = fmt->streams[i];
        printf("STREAM %u duration=%lld time_base=%d/%d tb_num_duration_sec=%f\n",
               i, (long long)st->duration, st->time_base.num, st->time_base.den,
               st->duration * av_q2d(st->time_base));
    }
    printf("FORMAT duration=%lld\n", (long long)fmt->duration);
    avformat_close_input(&fmt);
    return 0;
}
