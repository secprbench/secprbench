/*
 * Companion harness for the pre_intro (parent) revision of GH-19438.
 * Same rationale as harness_postintro.c: this container's curl has no
 * librtmp -dev headers, so lib/curl_rtmp.c compiles to nothing without
 * USE_LIBRTMP. This #includes the real, unmodified curl_rtmp.c for THIS
 * revision (parent of the intro commit), which still uses the old
 * conn->proto.rtmp field (no connection meta-hash yet).
 *
 * main() replays the same scenario: rtmp_setup_connection() hits a
 * URL-parse failure (RTMP_SetupURL fails), then we invoke rtmp_disconnect()
 * the way the old connection-teardown code did. In this revision,
 * conn->proto.rtmp is only assigned on the success path, so on failure it
 * stays NULL and rtmp_disconnect() must not free anything a second time.
 */
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define LOG(msg) write(2, msg, sizeof(msg) - 1)

static int g_free_count = 0;

#define USE_LIBRTMP 1
#include "curl_rtmp.c"

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
  return 0;
}
void RTMP_Close(RTMP *r) { (void)r; }
void RTMP_Free(RTMP *r) {
  g_free_count++;
  LOG("[harness] RTMP_Free() call\n");
  free(r);
}
int RTMP_Connect1(RTMP *r, void *x) { (void)r; (void)x; return 0; }
int RTMP_ConnectStream(RTMP *r, int s) { (void)r; (void)s; return 0; }
int RTMP_Read(RTMP *r, char *buf, int size) {
  (void)r; (void)buf; (void)size; return -1;
}
int RTMP_Write(RTMP *r, const char *buf, int size) {
  (void)r; (void)buf; (void)size; return -1;
}

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

/* ---- memory callbacks required once curl_memory.h redirects
 * malloc/calloc/free/strdup (see lib/curl_memory.h; active whenever
 * CURLDEBUG is not defined, which is the case in this build). ---- */
curl_malloc_callback  Curl_cmalloc  = (curl_malloc_callback)malloc;
curl_free_callback    Curl_cfree    = (curl_free_callback)free;
curl_realloc_callback Curl_crealloc = (curl_realloc_callback)realloc;
curl_strdup_callback  Curl_cstrdup  = (curl_strdup_callback)strdup;
curl_calloc_callback  Curl_ccalloc  = (curl_calloc_callback)calloc;

int main(void)
{
  struct Curl_easy easy;
  struct connectdata conn;
  CURLcode result;

  memset(&easy, 0, sizeof(easy));
  memset(&conn, 0, sizeof(conn));
  easy.state.url = strdup("rtmp://bad.example/app");

  LOG("[harness] calling rtmp_setup_connection()...\n");
  result = rtmp_setup_connection(&easy, &conn);
  (void)result;
  LOG("[harness] rtmp_setup_connection() returned\n");

  LOG("[harness] calling rtmp_disconnect() (old-style teardown)...\n");
  rtmp_disconnect(&easy, &conn, TRUE);

  LOG("[harness] done, no crash observed\n");
  free(easy.state.url);
  return 0;
}
