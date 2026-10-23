#define HAVE_CONFIG_H 1
#include "curl_setup.h"
#include "urldata.h"
#include "vtls/vtls.h"
#include <stdio.h>
#include <string.h>

int main(void)
{
  CURLcode rc;
  CURL *easy;
  unsigned char pubkey[32];

  memset(pubkey, 0x41, sizeof(pubkey));

  curl_global_init(CURL_GLOBAL_ALL);
  easy = curl_easy_init();
  if(!easy) {
    fprintf(stderr, "curl_easy_init failed\n");
    return 2;
  }

  rc = Curl_pin_peer_pubkey((struct Curl_easy *)easy, "/poc/pin.pem",
                            pubkey, sizeof(pubkey));
  printf("Curl_pin_peer_pubkey returned %d\n", (int)rc);

  curl_easy_cleanup(easy);
  curl_global_cleanup();
  return 0;
}
