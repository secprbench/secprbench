#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#include "libswscale/swscale.h"
#include "libavutil/pixdesc.h"
#include "libavutil/mem.h"
#include "libavutil/opt.h"
#include "libavutil/imgutils.h"

int main(int argc, char **argv) {
    enum AVPixelFormat srcFormat = AV_PIX_FMT_YUV420P16LE;
    enum AVPixelFormat dstFormat = AV_PIX_FMT_BGRA64BE;
    unsigned scaler = SWS_BILINEAR;
    int srcW = 32, srcH = 32, dstW = 32, dstH = 32;
    int do_sat = 1;
    double sat_mult = 8.0;
    double contrast_mult = 8.0;

    if (argc > 1) scaler = strtoul(argv[1], NULL, 0);
    if (argc > 5) { srcW = atoi(argv[2]); srcH = atoi(argv[3]); dstW = atoi(argv[4]); dstH = atoi(argv[5]); }
    if (argc > 6) do_sat = atoi(argv[6]);
    if (argc > 7) sat_mult = atof(argv[7]);
    if (argc > 8) contrast_mult = atof(argv[8]);

    uint8_t *src[4] = {0}, *dst[4] = {0};
    int srcStride[4] = {0}, dstStride[4] = {0};

    av_image_fill_linesizes(srcStride, srcFormat, srcW);
    av_image_fill_linesizes(dstStride, dstFormat, dstW);
    for (int i = 0; i < 4; i++) {
        srcStride[i] = FFALIGN(srcStride[i], 32);
        dstStride[i] = FFALIGN(dstStride[i], 32);
    }

    size_t srcSize[4] = {0}, dstSize[4] = {0};
    ptrdiff_t srcPd[4], dstPd[4];
    for (int i=0;i<4;i++){ srcPd[i]=srcStride[i]; dstPd[i]=dstStride[i]; }
    av_image_fill_plane_sizes(srcSize, srcFormat, srcH, srcPd);
    av_image_fill_plane_sizes(dstSize, dstFormat, dstH, dstPd);

    for (int i=0;i<4;i++) {
        if (srcSize[i]) src[i] = av_mallocz(srcSize[i]+64);
        if (dstSize[i]) dst[i] = av_mallocz(dstSize[i]+64);
    }

    int hshift, vshift;
    av_pix_fmt_get_chroma_sub_sample(srcFormat, &hshift, &vshift);
    int cw = AV_CEIL_RSHIFT(srcW, hshift);
    int ch = AV_CEIL_RSHIFT(srcH, vshift);
    int maxv = 65535;
    int neutral = 32768;

    uint16_t *y = (uint16_t*)src[0];
    for (int r=0;r<srcH;r++)
        for (int c=0;c<srcW;c++)
            y[r*(srcStride[0]/2)+c] = maxv/2;

    uint16_t *u = (uint16_t*)src[1];
    uint16_t *v = (uint16_t*)src[2];
    for (int r=0;r<ch;r++) {
        int last = (r == ch-1);
        int val = last ? 0 : neutral;
        for (int c=0;c<cw;c++) {
            u[r*(srcStride[1]/2)+c] = val;
            v[r*(srcStride[2]/2)+c] = val;
        }
    }

    struct SwsContext *sws = sws_alloc_context();
    if (!sws) { fprintf(stderr, "alloc fail\n"); return 1; }

    unsigned flags = scaler | SWS_FULL_CHR_H_INT | SWS_ACCURATE_RND;
    av_opt_set_int(sws, "sws_flags", flags, 0);
    av_opt_set_int(sws, "srcw", srcW, 0);
    av_opt_set_int(sws, "srch", srcH, 0);
    av_opt_set_int(sws, "dstw", dstW, 0);
    av_opt_set_int(sws, "dsth", dstH, 0);
    av_opt_set_int(sws, "src_format", srcFormat, 0);
    av_opt_set_int(sws, "dst_format", dstFormat, 0);
    av_opt_set(sws, "alphablend", "none", 0);

    int ret = sws_init_context(sws, NULL, NULL);
    if (ret < 0) { fprintf(stderr, "init fail %d\n", ret); return 1; }

    if (do_sat) {
        int *pinv, *ptab, srcRange, dstRange, brightness, contrast, saturation;
        sws_getColorspaceDetails(sws, &pinv, &srcRange, &ptab, &dstRange,
                                  &brightness, &contrast, &saturation);
        int inv_copy[4], tab_copy[4];
        memcpy(inv_copy, pinv, sizeof(inv_copy));
        memcpy(tab_copy, ptab, sizeof(tab_copy));
        int big_con = (int)(contrast_mult * (1 << 16));
        int big_sat = (int)(sat_mult * (1 << 16));
        int r2 = sws_setColorspaceDetails(sws, inv_copy, srcRange, tab_copy, dstRange,
                                           0, big_con, big_sat);
        fprintf(stderr, "setColorspaceDetails ret=%d sat_mult=%f con_mult=%f\n", r2, sat_mult, contrast_mult);
    }

    fprintf(stderr, "scaling %dx%d -> %dx%d\n", srcW, srcH, dstW, dstH);

    sws_scale(sws, (const uint8_t * const*)src, srcStride, 0, srcH, dst, dstStride);

    fprintf(stderr, "done, no crash\n");
    sws_freeContext(sws);
    for (int i=0;i<4;i++) { av_free(src[i]); av_free(dst[i]); }
    return 0;
}
