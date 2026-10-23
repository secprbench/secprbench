#!/bin/sh
# GH-26952 reproducer (AddressSanitizer use-after-free).
#
# Drives openssl's internal RCU API (ossl_rcu_lock_new(4, ...), i.e. >3 QPs,
# the bug's documented precondition) with many concurrent "victim" reader
# threads (each also doing its own writes) alongside fast "filler" writer
# threads, all hammering ossl_synchronize_rcu()/CRYPTO_free() on a small
# 4-slot circular qp pool. In the buggy revision, ossl_synchronize_rcu()'s
# retire-order signal (next_to_retire++ / broadcast / prior_lock unlock) is
# released before, instead of after, the busy-wait confirming the qp has
# zero active readers; this lets another writer race ahead, wrap the small
# qp pool, and have its own ossl_synchronize_rcu() call return (and its
# caller free the RCU-protected data) while a different, still-active
# straggler reader is genuinely still dereferencing that data -- a real
# heap-use-after-free, caught here by AddressSanitizer.
set -e
cd /work

cc -g -O1 -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer \
    -I/work/include -I/work -I/work/crypto \
    /poc/poc_orch3.c -o /tmp/poc3_asan -L/work -lcrypto -lpthread -ldl

ASAN_OPTIONS="halt_on_error=1 detect_leaks=0" timeout 60 /tmp/poc3_asan
echo "RESULT: NO_CRASH (reproducer completed without AddressSanitizer report)"
