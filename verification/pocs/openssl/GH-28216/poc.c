/*
 * PoC for GH-28216: missing unlock on cache->lock in
 * OSSL_DECODER_CTX_new_for_pkey() error path (crypto/encode_decode/decoder_pkey.c)
 * when lh_DECODER_CACHE_ENTRY_insert() fails (allocation failure).
 *
 * Strategy:
 *  1. Install a custom malloc (via CRYPTO_set_mem_functions) that fails,
 *     exactly once, the node allocation performed by OPENSSL_LH_insert()
 *     (crypto/lhash/lhash.c line 114: "nn = OPENSSL_malloc(sizeof(*nn))"),
 *     matched precisely by call-site file/line so no other allocation in
 *     the process is affected.
 *  2. Warm up the decoder-cache / provider / property caches with an
 *     initial, successful call to OSSL_DECODER_CTX_new_for_pkey() for
 *     keytype "RSA", selection=EVP_PKEY_KEYPAIR.
 *  3. Make a second ("triggering") call with a different `selection` value
 *     so the (keytype,input_type,input_structure,propquery,selection) cache
 *     key is new and a fresh DECODER_CACHE_ENTRY must be inserted, with the
 *     failing allocator armed. This is where cache->lock is taken for
 *     write and the induced insert failure is hit.
 *  4. Make a third ("probe") call, identical to the triggering call but
 *     with no induced failure. On a correct build this must succeed
 *     (return a non-NULL OSSL_DECODER_CTX) promptly, because cache->lock
 *     must have been released by the triggering call regardless of whether
 *     that call succeeded or failed. If OSSL_DECODER_CTX_new_for_pkey()
 *     leaked cache->lock on the insert-failure path, this probe call will
 *     either hang forever re-acquiring the write lock (bounded by alarm())
 *     or fail immediately with a locking error surfaced as a NULL return
 *     (e.g. because the underlying rwlock implementation detects the
 *     same-thread re-lock and returns an error instead of blocking).
 */
#include <openssl/decoder.h>
#include <openssl/evp.h>
#include <openssl/crypto.h>
#include <openssl/err.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>

static int armed = 0;
static int fail_done = 0;
static long hit_count = 0;

static int matches_target(const char *file, int line)
{
    const char *needle = "lhash.c";
    size_t flen, nlen;

    if (file == NULL)
        return 0;
    flen = strlen(file);
    nlen = strlen(needle);
    if (flen < nlen)
        return 0;
    if (strcmp(file + (flen - nlen), needle) != 0)
        return 0;
    return line == 114;
}

static void *my_malloc(size_t num, const char *file, int line)
{
    if (armed && matches_target(file, line)) {
        hit_count++;
        if (!fail_done) {
            fail_done = 1;
            fprintf(stderr, "[poc] forcing malloc failure at %s:%d (hit #%ld)\n",
                    file, line, hit_count);
            return NULL;
        }
    }
    return malloc(num);
}

static void *my_realloc(void *ptr, size_t num, const char *file, int line)
{
    (void)file; (void)line;
    return realloc(ptr, num);
}

static void my_free(void *ptr, const char *file, int line)
{
    (void)file; (void)line;
    free(ptr);
}

static void alarm_handler(int sig)
{
    (void)sig;
    fprintf(stderr, "[poc] RESULT: PROBE_TIMEOUT (cache->lock leaked -> deadlock)\n");
    _exit(42);
}

int main(void)
{
    OSSL_DECODER_CTX *dctx;
    EVP_PKEY *pkey1 = NULL, *pkey2 = NULL, *pkey3 = NULL;

    if (CRYPTO_set_mem_functions(my_malloc, my_realloc, my_free) != 1) {
        fprintf(stderr, "[poc] CRYPTO_set_mem_functions failed (too late?)\n");
        return 2;
    }

    /* 1. Warm-up call. */
    dctx = OSSL_DECODER_CTX_new_for_pkey(&pkey1, NULL, NULL, "RSA",
                                         EVP_PKEY_KEYPAIR, NULL, NULL);
    fprintf(stderr, "[poc] warm-up call returned %p\n", (void *)dctx);
    if (dctx == NULL) {
        ERR_print_errors_fp(stderr);
        fprintf(stderr, "[poc] warm-up call failed unexpectedly, aborting test\n");
        return 3;
    }
    OSSL_DECODER_CTX_free(dctx);

    /* 2. Triggering call: force the insert to fail while cache->lock is held. */
    armed = 1;
    dctx = OSSL_DECODER_CTX_new_for_pkey(&pkey2, NULL, NULL, "RSA",
                                         EVP_PKEY_PUBLIC_KEY, NULL, NULL);
    armed = 0;
    fprintf(stderr, "[poc] triggering call returned %p, hit_count=%ld, fail_done=%d\n",
            (void *)dctx, hit_count, fail_done);
    if (dctx != NULL)
        OSSL_DECODER_CTX_free(dctx);

    if (!fail_done) {
        fprintf(stderr, "[poc] RESULT: INCONCLUSIVE (never hit the target allocation site)\n");
        return 4;
    }

    if (dctx == NULL)
        fprintf(stderr, "[poc] triggering call failed as expected (insert error path checked/taken)\n");
    else
        fprintf(stderr, "[poc] triggering call succeeded despite forced allocation failure "
                        "(insert error not checked by this revision)\n");

    /* 3. Probe call: fully normal, no induced failure. Must succeed promptly
     *    on a correct build. */
    signal(SIGALRM, alarm_handler);
    alarm(8);
    dctx = OSSL_DECODER_CTX_new_for_pkey(&pkey3, NULL, NULL, "RSA",
                                         EVP_PKEY_PUBLIC_KEY, NULL, NULL);
    alarm(0);

    if (dctx != NULL) {
        fprintf(stderr, "[poc] RESULT: PROBE_OK (probe call returned a valid ctx promptly; "
                        "cache->lock was correctly released)\n");
        OSSL_DECODER_CTX_free(dctx);
        return 0;
    } else {
        fprintf(stderr, "[poc] RESULT: PROBE_FAIL (probe call returned NULL although no "
                        "failure was induced for it; consistent with a leaked cache->lock "
                        "causing the write-lock re-acquisition to fail)\n");
        ERR_print_errors_fp(stderr);
        return 1;
    }
}
