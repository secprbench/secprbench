/*
 * GH-27272: NULL pointer dereference in final_maxfragmentlen()
 *
 * final_maxfragmentlen() is an extension "finaliser" invoked by
 * tls_parse_all_extensions() for every ClientHello/ServerHello/
 * EncryptedExtensions regardless of whether the max_fragment_length
 * extension itself was present. In the vulnerable (post_intro) revision
 * the function unconditionally dereferences s->session before the
 * NULL check that guards the rest of the function, whereas upstream's
 * own analysis (and the fix) establish that s->session can legitimately
 * be NULL when this finaliser runs (e.g. around HelloRetryRequest /
 * session-less processing windows in the state machine).
 *
 * This harness drives the real internal extension-processing entry
 * points (tls_collect_extensions / tls_parse_all_extensions), exactly
 * as the TLS state machine does for an incoming ClientHello, on a
 * genuine SSL_CONNECTION produced by SSL_new(). It reproduces the
 * documented precondition (s->session == NULL at finaliser time) and
 * then lets the unmodified target code run normally.
 */
#include <string.h>
#include <stdio.h>
#include <openssl/ssl.h>
#include "internal/nelem.h"
#include "internal/cryptlib.h"
#include "../ssl_local.h"
#include "statem_local.h"

int main(void)
{
    SSL_CTX *ctx;
    SSL *ssl;
    SSL_CONNECTION *sc;
    RAW_EXTENSION *exts = NULL;
    PACKET pkt;
    static const unsigned char empty[1] = { 0 };

    ctx = SSL_CTX_new(TLS_server_method());
    if (ctx == NULL) {
        fprintf(stderr, "SSL_CTX_new failed\n");
        return 2;
    }

    ssl = SSL_new(ctx);
    if (ssl == NULL) {
        fprintf(stderr, "SSL_new failed\n");
        return 2;
    }

    sc = SSL_CONNECTION_FROM_SSL(ssl);
    if (sc == NULL) {
        fprintf(stderr, "SSL_CONNECTION_FROM_SSL failed\n");
        return 2;
    }

    sc->server = 1;

    /*
     * Reproduce the documented precondition: s->session is NULL when the
     * extension finalisers run for this ClientHello-context pass. This is
     * the exact invariant the fix commit (28de1f5004c1) establishes was
     * being violated: "s->session is checked for NULL after it was
     * dereferenced earlier."
     */
    SSL_SESSION_free(sc->session);
    sc->session = NULL;

    PACKET_buf_init(&pkt, (unsigned char *)empty, 0);

    if (!tls_collect_extensions(sc, &pkt, SSL_EXT_CLIENT_HELLO, &exts, NULL, 1)) {
        fprintf(stderr, "tls_collect_extensions failed\n");
        SSL_free(ssl);
        SSL_CTX_free(ctx);
        return 2;
    }

    /* This call reaches final_maxfragmentlen() with s->session == NULL */
    if (!tls_parse_all_extensions(sc, SSL_EXT_CLIENT_HELLO, exts, NULL, 0, 1)) {
        fprintf(stderr, "tls_parse_all_extensions returned failure (no crash)\n");
        OPENSSL_free(exts);
        SSL_free(ssl);
        SSL_CTX_free(ctx);
        return 1;
    }

    printf("NO CRASH: tls_parse_all_extensions completed with s->session == NULL\n");

    OPENSSL_free(exts);
    SSL_free(ssl);
    SSL_CTX_free(ctx);
    return 0;
}
