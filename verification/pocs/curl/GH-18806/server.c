/* minimal concurrent TLS 1.3 HTTP server, forks per connection, so that
   many handshakes / NewSessionTicket deliveries can happen truly in
   parallel (needed to make the curl ssl session-cache race observable). */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <openssl/ssl.h>
#include <openssl/err.h>

static const char *RESP =
  "HTTP/1.1 200 OK\r\nContent-Length: 13\r\nConnection: close\r\n\r\nhello world!\n";

int main(int argc, char **argv) {
  int port = argc > 1 ? atoi(argv[1]) : 8443;
  const char *certf = argc > 2 ? argv[2] : "cert.pem";
  const char *keyf = argc > 3 ? argv[3] : "key.pem";

  signal(SIGCHLD, SIG_IGN);

  SSL_CTX *ctx = SSL_CTX_new(TLS_server_method());
  if(!ctx) { ERR_print_errors_fp(stderr); return 1; }
  SSL_CTX_set_min_proto_version(ctx, TLS1_2_VERSION);
  if(SSL_CTX_use_certificate_file(ctx, certf, SSL_FILETYPE_PEM) != 1 ||
     SSL_CTX_use_PrivateKey_file(ctx, keyf, SSL_FILETYPE_PEM) != 1) {
    ERR_print_errors_fp(stderr);
    return 1;
  }
  /* make sure session tickets / resumption is on (default) and issue a
     couple of tickets like real servers do */
  SSL_CTX_set_num_tickets(ctx, 2);

  int lfd = socket(AF_INET, SOCK_STREAM, 0);
  int one = 1;
  setsockopt(lfd, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));
  struct sockaddr_in addr;
  memset(&addr, 0, sizeof(addr));
  addr.sin_family = AF_INET;
  addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
  addr.sin_port = htons((unsigned short)port);
  if(bind(lfd, (struct sockaddr*)&addr, sizeof(addr)) != 0) {
    perror("bind");
    return 1;
  }
  if(listen(lfd, 256) != 0) {
    perror("listen");
    return 1;
  }
  fprintf(stderr, "listening on %d\n", port);

  for(;;) {
    struct sockaddr_in cliaddr;
    socklen_t clilen = sizeof(cliaddr);
    int cfd = accept(lfd, (struct sockaddr*)&cliaddr, &clilen);
    if(cfd < 0) {
      if(errno == EINTR) continue;
      continue;
    }
    pid_t pid = fork();
    if(pid == 0) {
      /* child */
      close(lfd);
      SSL *ssl = SSL_new(ctx);
      SSL_set_fd(ssl, cfd);
      if(SSL_accept(ssl) <= 0) {
        _exit(0);
      }
      /* read the request (ignore content) */
      char buf[4096];
      SSL_read(ssl, buf, sizeof(buf));
      SSL_write(ssl, RESP, (int)strlen(RESP));
      /* give the stack a chance to flush post-handshake tickets before
         closing */
      SSL_shutdown(ssl);
      SSL_free(ssl);
      close(cfd);
      _exit(0);
    }
    else {
      close(cfd);
    }
  }
  return 0;
}
