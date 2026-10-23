#include <stdio.h>
#include <stdint.h>
#include "libavcodec/get_bits.h"

int main(void) {
    uint8_t buf[8] = {0xCC, 0x80, 0,0,0,0,0,0};
    GetBitContext gb;
    init_get_bits8(&gb, buf, sizeof(buf));
    printf("data_mode=%d\n", get_bits(&gb,2));
    printf("data_pair=%d\n", get_bits1(&gb));
    printf("coarse=%d\n", get_bits1(&gb));
    printf("freq_res=%d\n", get_bits(&gb,2));
    printf("pcm_coding=%d\n", get_bits1(&gb));
    printf("diff_freq_bit=%d\n", get_bits1(&gb));
    printf("dim=%d\n", get_bits1(&gb));
    return 0;
}
