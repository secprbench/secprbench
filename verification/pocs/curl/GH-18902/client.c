#include <curl/curl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static size_t discard(char *ptr, size_t size, size_t nmemb, void *opaque) {
  (void)ptr; (void)opaque;
  return size * nmemb;
}

int main(int argc, char **argv) {
  CURL *handle;
  CURLcode first, second;
  char url[256];
  if(argc != 5) return 2;
  if(curl_global_init(CURL_GLOBAL_DEFAULT) != CURLE_OK) return 3;
  handle = curl_easy_init();
  if(handle == NULL) return 4;
  snprintf(url, sizeof(url), "https://localhost:%s/", argv[1]);
  curl_easy_setopt(handle, CURLOPT_URL, url);
  curl_easy_setopt(handle, CURLOPT_CAINFO, argv[2]);
  curl_easy_setopt(handle, CURLOPT_SSL_VERIFYPEER, 1L);
  curl_easy_setopt(handle, CURLOPT_SSL_VERIFYHOST, 2L);
  curl_easy_setopt(handle, CURLOPT_SSL_VERIFYSTATUS, 1L);
  curl_easy_setopt(handle, CURLOPT_FORBID_REUSE, 1L);
  curl_easy_setopt(handle, CURLOPT_SSLVERSION,
                   CURL_SSLVERSION_TLSv1_2 | CURL_SSLVERSION_MAX_TLSv1_2);
  curl_easy_setopt(handle, CURLOPT_CONNECT_ONLY, 1L);
  curl_easy_setopt(handle, CURLOPT_VERBOSE, 1L);
  curl_easy_setopt(handle, CURLOPT_WRITEFUNCTION, discard);
  fprintf(stderr, "=== FIRST REQUEST ===\n");
  first = curl_easy_perform(handle);
  fprintf(stderr, "FIRST_RESULT=%d %s\n", (int)first, curl_easy_strerror(first));
  if(rename(argv[3], argv[4]) != 0) {
    perror("replace OCSP response");
    curl_easy_cleanup(handle);
    curl_global_cleanup();
    return 5;
  }
  fprintf(stderr, "=== SECOND REQUEST ===\n");
  second = curl_easy_perform(handle);
  fprintf(stderr, "SECOND_RESULT=%d %s\n", (int)second, curl_easy_strerror(second));
  curl_easy_cleanup(handle);
  curl_global_cleanup();
  return 0;
}
