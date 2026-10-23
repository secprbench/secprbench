/*
 * Standalone reproducer for openssl GH-26952: RCU qp retire-order race.
 * Uses the internal RCU API directly (ossl_rcu_*), mirroring
 * test/threadstest.c's _torture_rcu() synchronous-reclaim path but with
 * a larger QP pool and more concurrent writers to maximize the number of
 * writers pipelined through ossl_synchronize_rcu() at once (root cause
 * requires >3 QPs allocated).
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <pthread.h>
#include <unistd.h>
#include <stdatomic.h>
#include <time.h>
#include <openssl/crypto.h>
#include "internal/rcu.h"

#define NUM_QPS 8
#define NUM_WRITERS 8
#define NUM_READERS 32
#define RUN_SECONDS 30

static CRYPTO_RCU_LOCK *rcu_lock;
static uint64_t *writer_ptr = NULL;
static uint64_t global_ctr = 0;
static atomic_int stop_flag = 0;

static double now_secs(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec / 1e9;
}

static void *writer_fn(void *arg)
{
    uint64_t *old, *new;

    while (!atomic_load(&stop_flag)) {
        new = CRYPTO_zalloc(sizeof(uint64_t), NULL, 0);
        ossl_rcu_write_lock(rcu_lock);
        old = ossl_rcu_deref(&writer_ptr);
        *new = global_ctr++;
        ossl_rcu_assign_ptr(&writer_ptr, &new);
        ossl_rcu_write_unlock(rcu_lock);
        ossl_synchronize_rcu(rcu_lock);
        CRYPTO_free(old, NULL, 0);
    }
    return NULL;
}

static void *reader_fn(void *arg)
{
    uint64_t *valp;
    uint64_t val;

    while (!atomic_load(&stop_flag)) {
        ossl_rcu_read_lock(rcu_lock);
        valp = ossl_rcu_deref(&writer_ptr);
        val = (valp == NULL) ? 0 : *valp;
        (void)val;
        ossl_rcu_read_unlock(rcu_lock);
    }
    return NULL;
}

int main(void)
{
    pthread_t writers[NUM_WRITERS], readers[NUM_READERS];
    int i;
    double t0;

    rcu_lock = ossl_rcu_lock_new(NUM_QPS, NULL);
    if (rcu_lock == NULL) {
        fprintf(stderr, "FAIL: could not create rcu lock\n");
        return 1;
    }

    for (i = 0; i < NUM_READERS; i++)
        pthread_create(&readers[i], NULL, reader_fn, NULL);
    for (i = 0; i < NUM_WRITERS; i++)
        pthread_create(&writers[i], NULL, writer_fn, NULL);

    t0 = now_secs();
    while (now_secs() - t0 < RUN_SECONDS)
        usleep(100000);
    atomic_store(&stop_flag, 1);

    for (i = 0; i < NUM_WRITERS; i++)
        pthread_join(writers[i], NULL);
    for (i = 0; i < NUM_READERS; i++)
        pthread_join(readers[i], NULL);

    ossl_rcu_lock_free(rcu_lock);
    printf("DONE: no crash observed (writes=%llu)\n", (unsigned long long)global_ctr);
    return 0;
}
