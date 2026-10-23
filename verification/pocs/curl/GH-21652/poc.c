#include <stdio.h>
#include <string.h>
#include <curl/curl.h>

int main(void) {
  CURLU *u = curl_url();
  CURLUcode rc = curl_url_set(u, CURLUPART_URL, "http://1.2.3.0x/", 0);
  printf("set rc=%d\n", rc);
  if(!rc) {
    char *host = NULL;
    rc = curl_url_get(u, CURLUPART_HOST, &host, 0);
    printf("get rc=%d host=[%s]\n", rc, host ? host : "(null)");
    if(host) {
      if(!strcmp(host, "1.2.3.0x"))
        printf("OBSERVATION: host unchanged (not treated as IPv4)\n");
      else
        printf("OBSERVATION: host NORMALIZED to [%s] (treated as IPv4, BUG)\n", host);
      curl_free(host);
    }
  }
  else {
    printf("OBSERVATION: url set failed, rc=%d\n", rc);
  }
  curl_url_cleanup(u);
  return 0;
}
