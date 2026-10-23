int main(void) {
    AVCodecContext *c = avcodec_alloc_context3(NULL);
    AVFrame *frame = av_frame_alloc();
    Libdav1dContext dav1d;
    Dav1dPicture pic;
    Dav1dITUTT35 t35;
    uint8_t *heap_payload;
    int res;

    memset(&dav1d, 0, sizeof(dav1d));
    memset(&pic, 0, sizeof(pic));

    /* Exactly 1-byte heap allocation for the T.35 payload: country_code=US
     * (0xB5) with a payload shorter than the 2 bytes needed for
     * provider_code, per the reporter's PoC description (crafted AV1 IVF
     * with ITU-T T.35 metadata OBU, country_code=0xB5, 1-byte payload).
     * Plain malloc (not av_malloc, which over-allocates/pads for SIMD
     * alignment and would hide a 1-byte overread from ASan's redzone) so
     * the ASan heap redzone sits immediately after the 1 logical byte. */
    heap_payload = malloc(1);
    if (!heap_payload) { fprintf(stderr, "alloc failed\n"); return 2; }
    heap_payload[0] = 0x00;

    t35.country_code = ITU_T_T35_COUNTRY_CODE_US; /* 0xB5 */
    t35.country_code_extension_byte = 0;
    t35.payload = heap_payload;
    t35.payload_size = 1;

    res = parse_itut_t35_metadata(&dav1d, &pic, &t35, c, frame);
    printf("PARSE_RESULT=%d\n", res);

    free(heap_payload);
    av_frame_free(&frame);
    avcodec_free_context(&c);
    printf("DONE_NO_CRASH\n");
    return 0;
}
