#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#include "libavcodec/cbs.h"
#include "libavutil/log.h"

int main(int argc, char **argv)
{
    if (argc < 2) {
        fprintf(stderr, "usage: %s <input-file>\n", argv[0]);
        return 2;
    }

    FILE *f = fopen(argv[1], "rb");
    if (!f) { perror("fopen"); return 2; }
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    uint8_t *data = av_malloc(sz + AV_INPUT_BUFFER_PADDING_SIZE);
    if (!data) return 2;
    memset(data, 0, sz + AV_INPUT_BUFFER_PADDING_SIZE);
    if (fread(data, 1, sz, f) != (size_t)sz) { perror("fread"); return 2; }
    fclose(f);

    av_log_set_level(AV_LOG_DEBUG);

    CodedBitstreamContext *ctx = NULL;
    int err = ff_cbs_init(&ctx, AV_CODEC_ID_APV, NULL);
    if (err < 0) {
        fprintf(stderr, "ff_cbs_init failed: %d\n", err);
        return 1;
    }

    CodedBitstreamFragment frag = { 0 };

    err = ff_cbs_read(ctx, &frag, data, sz);
    fprintf(stderr, "ff_cbs_read -> %d (nb_units=%d)\n", err, frag.nb_units);
    if (err < 0) {
        fprintf(stderr, "read failed, stopping (no bug reachable)\n");
        ff_cbs_fragment_free(&frag);
        ff_cbs_close(&ctx);
        return 0;
    }

    /* Round-trip: re-serialize the parsed fragment. This exercises the
     * write-direction tile() code path (ff_copy_bits) with the
     * unchecked tile_data_size read out of the bitstream, which is
     * exactly the sink used by cbs_apv_write_unit / ff_cbs_write_fragment_data
     * in the real oss-fuzz BSF_APV_METADATA / round-trip fuzzers. */
    err = ff_cbs_write_fragment_data(ctx, &frag);
    fprintf(stderr, "ff_cbs_write_fragment_data -> %d\n", err);

    ff_cbs_fragment_free(&frag);
    ff_cbs_close(&ctx);

    fprintf(stderr, "DONE_NO_CRASH\n");
    return 0;
}
