/* PoC driver for Curl_get_line(), pre-refactor 2-arg signature:
 *   int Curl_get_line(struct dynbuf *buf, FILE *input);
 * See poc_new.c for rationale.
 */
#define _GNU_SOURCE
#include "curl_setup.h"
#include "curl_get_line.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <signal.h>
#include <unistd.h>

static void alarm_handler(int sig)
{
  (void)sig;
  static const char msg[] = "TIMEOUT_HANG: Curl_get_line did not return within 5s\n";
  write(2, msg, sizeof(msg) - 1);
  _exit(42);
}

static ssize_t err_read(void *cookie, char *buf, size_t size)
{
  (void)cookie; (void)buf; (void)size;
  errno = EIO;
  return -1; /* persistent I/O error, never EOF */
}

static cookie_io_functions_t io_funcs = {
  .read = err_read,
  .write = NULL,
  .seek = NULL,
  .close = NULL,
};

int main(void)
{
  FILE *input = fopencookie(NULL, "r", io_funcs);
  if(!input) {
    perror("fopencookie");
    return 1;
  }

  struct dynbuf buf;
  curlx_dyn_init(&buf, 64 * 1024);

  signal(SIGALRM, alarm_handler);
  alarm(5);

  int result = Curl_get_line(&buf, input);

  alarm(0);
  printf("RESULT=%d LEN=%zu\n", result, curlx_dyn_len(&buf));

  curlx_dyn_free(&buf);
  fclose(input);
  return 0;
}
