/*
 * Unit-level PoC harness for GH-19438 (curl RTMP double-free on URL parse
 * error). This container's curl was configured WITHOUT librtmp
 * (`--with-librtmp` not detected: only the runtime .so.1 is installed, no
 * -dev headers), so `curl rtmp://...` never reaches lib/curl_rtmp.c at all
 * (the file compiles to an empty translation unit without USE_LIBRTMP).
 *
 * To exercise the actual, unmodified lib/curl_rtmp.c from this revision,
 * this harness #includes it directly (with -DUSE_LIBRTMP=1 and a tiny
 * stand-in <librtmp/rtmp.h>, rtmp_stub.h, added under /poc), which makes
 * its normally-static rtmp_setup_connection()/rtmp_conn_dtor() callable
 * from main() below in the same translation unit. It links against the
 * project's real lib/hash.c object (already built for this exact
 * revision), so Curl_conn_meta_set/remove go through the actual
 * Curl_hash implementation used by the real connection teardown code.
 *
 * main() replays what curl does for a malformed RTMP URL:
 *   1. call rtmp_setup_connection(data, conn) -- the fake RTMP_SetupURL()
 *      reports a parse failure the way librtmp does for a bad URL.
 *   2. on that failure path, tear the connection down the way url.c does
 *      when connection setup fails: destroy conn->meta_hash, invoking
 *      every stored meta destructor exactly once (rtmp_conn_dtor in the
 *      post-refactor code).
 *
 * RTMP_Free() below calls the real libc free() on the RTMP* -- so if
 * lib/curl_rtmp.c frees the same pointer twice (manually on the error
 * path, and again from rtmp_conn_dtor() during meta_hash teardown), the
 * AddressSanitizer this binary is built with reports a real double-free,
 * exactly as the full curl binary would if RTMP support were compiled in.
 *
 * NOTE: this file avoids stdio *printf functions in its own logging
 * because curl_printf.h (pulled in transitively) #defines fprintf and
 * friends to curl_m*printf, which are not linked into this minimal
 * harness; plain write(2, ...) sidesteps that entirely.
 */
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define LOG(msg) write(2, msg, sizeof(msg) - 1)

static int g_free_count = 0;

#define USE_LIBRTMP 1
#include "curl_rtmp.c"   /* pulls in curl_setup.h/urldata.h/url.h/rtmp_stub.h
                             and makes the static functions visible here */

int curlx_uztosi(size_t uznum) { return (int)uznum; }

RTMP *RTMP_Alloc(void) {
  RTMP *r = (RTMP *)calloc(1, sizeof(RTMP));
  LOG("[harness] RTMP_Alloc\n");
  return r;
}
void RTMP_Init(RTMP *r) { (void)r; }
void RTMP_SetBufferMS(RTMP *r, int ms) { (void)r; (void)ms; }
int RTMP_SetupURL(RTMP *r, char *url) {
  (void)r; (void)url;
  LOG("[harness] RTMP_SetupURL -> failure (simulated bad URL)\n");
  return 0; /* simulate the librtmp URL parse failure the report hits */
}
void RTMP_Close(RTMP *r) { (void)r; }
void RTMP_Free(RTMP *r) {
  g_free_count++;
  LOG("[harness] RTMP_Free() call\n");
  free(r); /* real free(); ASAN flags it if r was already freed */
}
int RTMP_Connect1(RTMP *r, void *x) { (void)r; (void)x; return 0; }
int RTMP_ConnectStream(RTMP *r, int s) { (void)r; (void)s; return 0; }
int RTMP_Read(RTMP *r, char *buf, int size) {
  (void)r; (void)buf; (void)size; return -1;
}
int RTMP_Write(RTMP *r, const char *buf, int size) {
  (void)r; (void)buf; (void)size; return -1;
}

/* ---- stubs for other curl internals referenced by unreached code in
 * lib/curl_rtmp.c (rtmp_do/rtmp_connect/rtmp_recv/rtmp_send/version are
 * never invoked by this harness, but the linker still needs definitions
 * since they live in the same translation unit). ---- */
int curlx_nonblock(curl_socket_t sockfd, int nonblock) {
  (void)sockfd; (void)nonblock; return 0;
}
void Curl_pgrsSetUploadSize(struct Curl_easy *data, curl_off_t size) {
  (void)data; (void)size;
}
void Curl_xfer_setup1(struct Curl_easy *data, int send_recv,
                       curl_off_t recv_size, bool getheader) {
  (void)data; (void)send_recv; (void)recv_size; (void)getheader;
}
int curl_msnprintf(char *buffer, size_t maxlength, const char *format, ...) {
  (void)buffer; (void)maxlength; (void)format; return 0;
}

/* ---- memory callbacks required by lib/hash.c (see lib/curl_memory.h) ---- */
curl_malloc_callback  Curl_cmalloc  = (curl_malloc_callback)malloc;
curl_free_callback    Curl_cfree    = (curl_free_callback)free;
curl_realloc_callback Curl_crealloc = (curl_realloc_callback)realloc;
curl_strdup_callback  Curl_cstrdup  = (curl_strdup_callback)strdup;
curl_calloc_callback  Curl_ccalloc  = (curl_calloc_callback)calloc;

/* ---- real Curl_conn_meta_*, copied verbatim from lib/url.c so we do not
 * need to link the rest of url.c's dependency graph. Same semantics: a
 * thin wrapper around Curl_hash_add2/delete/pick on conn->meta_hash. ---- */
CURLcode Curl_conn_meta_set(struct connectdata *conn, const char *key,
                            void *meta_data, Curl_meta_dtor *meta_dtor)
{
  if(!Curl_hash_add2(&conn->meta_hash, (void *)(size_t)key, strlen(key) + 1,
                     meta_data, meta_dtor)) {
    meta_dtor((void *)(size_t)key, strlen(key) + 1, meta_data);
    return CURLE_OUT_OF_MEMORY;
  }
  return CURLE_OK;
}

void Curl_conn_meta_remove(struct connectdata *conn, const char *key)
{
  Curl_hash_delete(&conn->meta_hash, (void *)(size_t)key, strlen(key) + 1);
}

void *Curl_conn_meta_get(struct connectdata *conn, const char *key)
{
  return Curl_hash_pick(&conn->meta_hash, (void *)(size_t)key, strlen(key) + 1);
}

int main(void)
{
  struct Curl_easy easy;
  struct connectdata conn;
  CURLcode result;

  memset(&easy, 0, sizeof(easy));
  memset(&conn, 0, sizeof(conn));
  easy.state.url = strdup("rtmp://bad.example/app");

  Curl_hash_init(&conn.meta_hash, 23, Curl_hash_str, Curl_str_key_compare,
                 NULL);

  LOG("[harness] calling rtmp_setup_connection()...\n");
  result = rtmp_setup_connection(&easy, &conn);
  (void)result;
  LOG("[harness] rtmp_setup_connection() returned\n");

  /* This is what url.c's connection teardown does: destroy the
   * connection's meta hash, invoking every stored destructor exactly
   * once. If RTMP_Free() was already called manually on the error path
   * above, this second free of the same pointer is the double free. */
  LOG("[harness] tearing down conn->meta_hash "
      "(invokes rtmp_conn_dtor if 'r' is still registered)...\n");
  Curl_hash_destroy(&conn.meta_hash);

  LOG("[harness] done, no crash observed\n");
  free(easy.state.url);
  return 0;
}
