#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stddef.h>

/* Force all RISC-V capability bits on (ZBB=bit1, V=bit14, ZVBB=bit15, ZVKB=bit17) */
uint32_t OPENSSL_riscvcap_P[1] = { 0xFFFFFFFFu };

size_t riscv_vlen(void) { return 128; }

static const char *last_called = "none";

void ChaCha20_ctr32_c(unsigned char *out, const unsigned char *inp, size_t len,
                      const unsigned int key[8], const unsigned int counter[4])
{
    last_called = "C_SCALAR";
    if (out && inp && len)
        memmove(out, inp, len);
}

/* pre_intro symbol */
void ChaCha20_ctr32_zbb_zvkb(unsigned char *out, const unsigned char *inp, size_t len,
                              const unsigned int key[8], const unsigned int counter[4])
{
    last_called = "ZBB_ZVKB_NOVEC";
    if (out && inp && len)
        memmove(out, inp, len);
}

/* post_intro / post_benign symbols */
void ChaCha20_ctr32_v_zbb_zvkb(unsigned char *out, const unsigned char *inp, size_t len,
                                const unsigned int key[8], const unsigned int counter[4])
{
    last_called = "VECTOR_V_ZBB_ZVKB";
    if (out && inp && len)
        memmove(out, inp, len);
}

void ChaCha20_ctr32_v_zbb(unsigned char *out, const unsigned char *inp, size_t len,
                          const unsigned int key[8], const unsigned int counter[4])
{
    last_called = "VECTOR_V_ZBB";
    if (out && inp && len)
        memmove(out, inp, len);
}

extern void ChaCha20_ctr32(unsigned char *out, const unsigned char *inp, size_t len,
                           const unsigned int key[8], const unsigned int counter[4]);

int main(void)
{
    static unsigned char buf_out[512];
    static unsigned char buf_in[512];
    unsigned int key[8] = {0};
    unsigned int counter[4] = {0};
    /* Deliberately misalign both pointers by 1 byte relative to sizeof(size_t) */
    unsigned char *out = buf_out + 1;
    unsigned char *inp = buf_in + 1;
    size_t len = 200; /* > CHACHA_BLK_SIZE (64) so length gate passes */

    memset(buf_in, 0x41, sizeof(buf_in));

    ChaCha20_ctr32(out, inp, len, key, counter);
    printf("DISPATCH=%s\n", last_called);
    return 0;
}
