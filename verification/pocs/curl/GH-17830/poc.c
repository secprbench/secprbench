/*
 * PoC for curl GH-17830: lib/vtls/rustls.c's ECH command-line config path
 * base64-decodes into a buffer obtained through curl's internal, overridable
 * allocator (Curl_base64_decode -> malloc() macro -> Curl_cmalloc, see
 * lib/curl_memory.h), but (in the introduced-bug revision) releases it with
 * the plain libc free(), because rustls.c never includes curl_memory.h /
 * memdebug.h. That mismatch is invisible when no allocator override is
 * active, but corrupts the heap / crashes once curl's memory function
 * overrides are engaged (curl_global_init_mem()), exactly as described in
 * the fix commit message.
 *
 * rustls.c itself cannot be linked in this environment (no rustls-ffi
 * library, no network access to build it), so this harness exercises the
 * real, unmodified lib/base64.c allocation function that rustls.c calls,
 * combined with the *exact* cleanup logic copied from each reviewed
 * revision of lib/vtls/rustls.c's init_config_builder_ech(), under a real
 * (documented, public-API) curl memory-function override -- the condition
 * the bug report says is required to turn the mismatch into a real bug.
 */
#include <curl/curl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Mirrors the layout of curl's own built-in memory-tracking allocator
 * (lib/memdebug.c: struct memdebug { size_t size; ... unsigned char mem[1];
 * }, curl_dbg_malloc returns &mem[0]) -- i.e. the pointer handed back to the
 * caller is offset from the real malloc() block. This models a real,
 * supported application use of curl_global_init_mem() with a bookkeeping
 * allocator.
 */
struct hdr { size_t size; };

static void *ov_malloc(size_t size)
{
  struct hdr *h = (struct hdr *)malloc(sizeof(struct hdr) + size);
  if(!h)
    return NULL;
  h->size = size;
  return (void *)(h + 1);
}
static void ov_free(void *ptr)
{
  struct hdr *h;
  if(!ptr)
    return;
  h = ((struct hdr *)ptr) - 1;
  free(h);
}
static void *ov_realloc(void *ptr, size_t size)
{
  struct hdr *h, *nh;
  if(!ptr)
    return ov_malloc(size);
  h = ((struct hdr *)ptr) - 1;
  nh = (struct hdr *)realloc(h, sizeof(struct hdr) + size);
  if(!nh)
    return NULL;
  nh->size = size;
  return (void *)(nh + 1);
}
static char *ov_strdup(const char *s)
{
  size_t l = strlen(s) + 1;
  char *p = (char *)ov_malloc(l);
  if(p)
    memcpy(p, s, l);
  return p;
}
static void *ov_calloc(size_t nmemb, size_t size)
{
  size_t total = nmemb * size;
  void *p = ov_malloc(total);
  if(p)
    memset(p, 0, total);
  return p;
}

/* Real, unmodified internal libcurl function (lib/base64.c), unchanged
 * across all three reviewed revisions, and the exact function
 * lib/vtls/rustls.c's init_config_builder_ech() calls for
 * `--ech-config <b64>`. It allocates its output buffer with malloc(), which
 * lib/base64.c (BUILDING_LIBCURL) has redefined via curl_memory.h to
 * Curl_cmalloc() -- the overridable allocator. */
extern CURLcode Curl_base64_decode(const char *src,
                                    unsigned char **outptr, size_t *outlen);

int main(int argc, char **argv)
{
  const char *b64 = (argc > 1) ? argv[1] : "AAAAAAAAAAAAAAAA";
  unsigned char *ech_config = NULL;
  size_t ech_config_len = 0;
  CURLcode decode_result;

  if(curl_global_init_mem(CURL_GLOBAL_ALL, ov_malloc, ov_free, ov_realloc,
                           ov_strdup, ov_calloc) != CURLE_OK) {
    fprintf(stderr, "curl_global_init_mem failed\n");
    return 2;
  }

  /* This is exactly the call in init_config_builder_ech():
   *   decode_result = Curl_base64_decode(b64, &ech_config, &ech_config_len);
   */
  decode_result = Curl_base64_decode(b64, &ech_config, &ech_config_len);
  if(decode_result || !ech_config) {
    fprintf(stderr, "base64 decode failed\n");
    curl_global_cleanup();
    return 3;
  }
  fprintf(stderr, "decoded %zu bytes at %p\n", ech_config_len,
          (void *)ech_config);

#if CLEANUP_MODE == 1
  /* Verbatim from post_intro lib/vtls/rustls.c (460ead61b6fe), cleanup:
   *   if(data->set.tls_ech & CURLECH_CLA_CFG && data->set.str[...]) {
   *     free(ech_config);
   *   }
   * rustls.c does not include curl_memory.h/memdebug.h, so this free() is
   * the plain libc free(), NOT curl's (possibly overridden) Curl_cfree(). */
  free(ech_config);
  fprintf(stderr, "freed via libc free()\n");
#elif CLEANUP_MODE == 2
  /* Verbatim from the fixed lib/vtls/rustls.c (cbf261e2de9f): rustls.c now
   * includes curl_memory.h + memdebug.h, so its free(ptr) call is macro
   * expanded to the overridable Curl_cfree(ptr). curl_free() is the public
   * API entry point for that exact same function. */
  curl_free(ech_config);
  fprintf(stderr, "freed via curl_free()\n");
#else
  /* pre_intro lib/vtls/rustls.c (before 460ead61b6fe) never freed
   * ech_config on this path at all (a plain leak, not an invalid free).
   * Free it correctly here so this harness itself doesn't leak. */
  curl_free(ech_config);
  fprintf(stderr, "(reference) freed via curl_free(); pre_intro leaked here\n");
#endif

  curl_global_cleanup();
  fprintf(stderr, "OK\n");
  return 0;
}
