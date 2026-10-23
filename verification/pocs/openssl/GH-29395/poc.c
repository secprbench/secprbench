/*
 * PoC for GH-29395: BIO_sendmmsg()/BIO_recvmmsg() invoke the legacy
 * BIO_CB_RETURN callback with a non-zero inret but a NULL `processed`
 * out-pointer. bio_call_callback() dereferences that NULL pointer
 * whenever a legacy (non-_ex) callback is installed and the underlying
 * bsendmmsg() call reports ret > 0.
 *
 * We install a trivial custom BIO_METHOD whose bsendmmsg() always
 * "succeeds" (returns 1, processed = num_msg), and register a legacy
 * BIO_set_callback() handler, then call BIO_sendmmsg().
 */
#define OPENSSL_SUPPRESS_DEPRECATED
#include <stdio.h>
#include <string.h>
#include <openssl/bio.h>
#include <openssl/crypto.h>

static int dummy_create(BIO *b)
{
    BIO_set_init(b, 1);
    return 1;
}

static int dummy_destroy(BIO *b)
{
    return 1;
}

static int dummy_sendmmsg(BIO *b, BIO_MSG *msg, size_t stride,
                           size_t num_msg, uint64_t flags,
                           size_t *msgs_processed)
{
    /* Pretend we successfully sent everything */
    *msgs_processed = num_msg;
    return 1;
}

static long legacy_cb(BIO *b, int oper, const char *argp, int argi,
                       long argl, long ret)
{
    fprintf(stderr, "legacy_cb called: oper=%d ret=%ld\n", oper, ret);
    return ret;
}

int main(void)
{
    BIO_METHOD *meth;
    BIO *b;
    BIO_MSG msg;
    size_t processed = 0;
    int ret;
    char data[16] = "hello";

    meth = BIO_meth_new(BIO_TYPE_SOCKET, "dummy-mmsg");
    if (meth == NULL) {
        fprintf(stderr, "BIO_meth_new failed\n");
        return 2;
    }
    BIO_meth_set_create(meth, dummy_create);
    BIO_meth_set_destroy(meth, dummy_destroy);
    BIO_meth_set_sendmmsg(meth, dummy_sendmmsg);

    b = BIO_new(meth);
    if (b == NULL) {
        fprintf(stderr, "BIO_new failed\n");
        return 2;
    }

    /* Install a LEGACY (non-_ex) callback to hit the vulnerable path */
    BIO_set_callback(b, legacy_cb);

    memset(&msg, 0, sizeof(msg));
    msg.data = data;
    msg.data_len = sizeof(data);

    ret = BIO_sendmmsg(b, &msg, sizeof(msg), 1, 0, &processed);
    fprintf(stderr, "BIO_sendmmsg returned %d, processed=%zu\n",
            ret, processed);

    BIO_free(b);
    BIO_meth_free(meth);

    printf("NO_CRASH: completed successfully\n");
    return 0;
}
