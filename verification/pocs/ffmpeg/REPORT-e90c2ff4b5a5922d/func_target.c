static int parse_itut_t35_metadata(Libdav1dContext *dav1d, Dav1dPicture *p,
                                   const Dav1dITUTT35 *itut_t35, AVCodecContext *c,
                                   AVFrame *frame) {
    GetByteContext gb;
    int provider_code, country_code;
    int res;

    bytestream2_init(&gb, itut_t35->payload, itut_t35->payload_size);

    country_code = itut_t35->country_code;
    switch (country_code) {
    case ITU_T_T35_COUNTRY_CODE_US:
        if (bytestream2_get_bytes_left(&gb) < 2)
            return AVERROR_INVALIDDATA;
        provider_code = bytestream2_get_be16u(&gb);

        switch (provider_code) {
        case ITU_T_T35_PROVIDER_CODE_ATSC: {
            uint32_t user_identifier = bytestream2_get_be32(&gb);
            switch (user_identifier) {
            case MKBETAG('G', 'A', '9', '4'): { // closed captions
                AVBufferRef *buf = NULL;

                res = ff_parse_a53_cc(&buf, gb.buffer, bytestream2_get_bytes_left(&gb));
                if (res < 0)
                    return res;
                if (!res)
                    return 0;  // no cc found, ignore

                res = ff_frame_new_side_data_from_buf(c, frame, AV_FRAME_DATA_A53_CC, &buf);
                if (res < 0)
                    return res;

#if FF_API_CODEC_PROPS
FF_DISABLE_DEPRECATION_WARNINGS
                c->properties |= FF_CODEC_PROPERTY_CLOSED_CAPTIONS;
FF_ENABLE_DEPRECATION_WARNINGS
#endif
                break;
            }
            default: // ignore unsupported identifiers
                break;
            }
            break;
        }
        case ITU_T_T35_PROVIDER_CODE_SAMSUNG: {
            AVDynamicHDRPlus *hdrplus;
            int provider_oriented_code = bytestream2_get_be16(&gb);
            int application_identifier = bytestream2_get_byte(&gb);

            if (provider_oriented_code != 1 || application_identifier != 4)
                return 0; // ignore

            hdrplus = av_dynamic_hdr_plus_create_side_data(frame);
            if (!hdrplus)
                return AVERROR(ENOMEM);

            res = av_dynamic_hdr_plus_from_t35(hdrplus, gb.buffer,
                                                bytestream2_get_bytes_left(&gb));
            if (res < 0)
                return res;
            break;
        }
        case ITU_T_T35_PROVIDER_CODE_DOLBY: {
            int provider_oriented_code = bytestream2_get_be32(&gb);
            if (provider_oriented_code != 0x800)
                return 0; // ignore

            res = ff_dovi_rpu_parse(&dav1d->dovi, gb.buffer, bytestream2_get_bytes_left(&gb),
                                    c->err_recognition);
            if (res < 0) {
                av_log(c, AV_LOG_WARNING, "Error parsing DOVI OBU.\n");
                return 0; // ignore
            }

            res = ff_dovi_attach_side_data(&dav1d->dovi, frame);
            if (res < 0)
                return res;
            break;
        }
        default:
            break;
        }
        break;
    default:
        // ignore unsupported provider codes
        break;
    }
    return 0;
}
