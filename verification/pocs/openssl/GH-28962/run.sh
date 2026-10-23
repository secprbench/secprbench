#!/bin/sh
set -e
cd /work
gcc -g -O1 -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer \
  -I. -Iinclude -Icrypto/x509 -Iproviders/common/include -Iproviders/implementations/include \
  /poc/poc.c -o /tmp/poc \
  ./libssl.a ./libcrypto.a -lpthread -ldl
/tmp/poc
