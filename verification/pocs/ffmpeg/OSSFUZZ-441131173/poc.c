#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "libavcodec/exif.h"
#include "libavutil/dict.h"

int main(void) {
    AVExifMetadata ifd = {0};
    AVDictionary *dict = NULL;
    int ret;

    /* Simulate how AV_TIFF_STRING values are actually produced by the EXIF
     * parser: av_mallocz(count + 1) -- i.e. count data bytes plus one
     * trailing NUL byte, exactly count+1 bytes allocated total. */
    const uint32_t N = 16;
    uint8_t *val = malloc(N + 1);
    if (!val) return 1;
    memset(val, 'A', N);
    val[N] = '\0';

    ret = av_exif_set_entry(NULL, &ifd, 0x010E /* ImageDescription */, AV_TIFF_STRING,
                             N, NULL, 0, val);
    fprintf(stderr, "av_exif_set_entry ret=%d\n", ret);
    free(val);
    if (ret < 0)
        return 2;

    ret = av_exif_ifd_to_dict(NULL, &ifd, &dict);
    fprintf(stderr, "av_exif_ifd_to_dict ret=%d\n", ret);

    AVDictionaryEntry *e = NULL;
    while ((e = av_dict_get(dict, "", e, AV_DICT_IGNORE_SUFFIX)))
        fprintf(stderr, "entry: %s = %s\n", e->key, e->value);

    av_dict_free(&dict);
    av_exif_free(&ifd);

    fprintf(stderr, "POC DONE OK\n");
    return 0;
}
