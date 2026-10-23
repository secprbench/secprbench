/*
 * GH-26952 amplifier v3: many CONCURRENT victim+slow-reader pairs (not
 * just one), each with an independent, randomly-sized/timed stall,
 * running continuously alongside fast filler writers against a small
 * (4-slot, i.e. >3 QP) qp pool. The goal is to let the writers_alloced
 * under-counting caused by the buggy early retire-order signal compound
 * across many independent stall events, so that two genuinely
 * independent (not reader-coupled) RCU epochs collide on one physical
 * qp and a writer frees data that a still-active, unrelated reader is
 * using -- a real, sanitizer-visible use-after-free.
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <pthread.h>
#include <unistd.h>
#include <stdatomic.h>
#include <string.h>
#include <openssl/crypto.h>
#include "internal/rcu.h"

#define NUM_QPS 4
#define NUM_FILLERS 8
#define NUM_VICTIM_THREADS 12
#define ROUNDS_PER_VICTIM 300
#define RUN_SECONDS 25

struct blob {
    uint64_t magic;
    uint64_t seq;
    char pad[64];
};

static CRYPTO_RCU_LOCK *rcu_lock;
static struct blob *writer_ptr = NULL;
static atomic_ulong global_seq = 0;
static atomic_int stop_flag = 0;
static unsigned seedbase = 12345;

static unsigned xrand(unsigned *s)
{
    *s = (*s) * 1103515245u + 12345u;
    return (*s >> 16) & 0x7fff;
}

static void *filler_writer_fn(void *arg)
{
    struct blob *old, *new;

    while (!atomic_load(&stop_flag)) {
        new = CRYPTO_zalloc(sizeof(*new), NULL, 0);
        new->magic = 0xF111; 
        ossl_rcu_write_lock(rcu_lock);
        old = ossl_rcu_deref(&writer_ptr);
        new->seq = atomic_fetch_add(&global_seq, 1);
        ossl_rcu_assign_ptr(&writer_ptr, &new);
        ossl_rcu_write_unlock(rcu_lock);
        ossl_synchronize_rcu(rcu_lock);
        if (old != NULL) {
            /* touch it before freeing: would already explode here if a
             * concurrent reader's earlier free already happened on this
             * exact chunk via our own race */
            old->magic = 0xDEAD0001;
            CRYPTO_free(old, NULL, 0);
        }
    }
    return NULL;
}

static void *victim_thread_fn(void *arg)
{
    long idx = (long)arg;
    unsigned seed = seedbase + (unsigned)idx * 7919u;
    int r;

    for (r = 0; r < ROUNDS_PER_VICTIM && !atomic_load(&stop_flag); r++) {
        struct blob *old, *new, *valp;
        unsigned sleep_us = 200 + (xrand(&seed) % 3000); /* 0.2-3.2ms */

        /* reader side: grab a reference, hold it for a random short time */
        ossl_rcu_read_lock(rcu_lock);
        valp = ossl_rcu_deref(&writer_ptr);
        if (valp != NULL && valp->magic != 0xF111 && valp->magic != 0xBEEF) {
            fprintf(stderr, "[victim %ld] UAF SIGNATURE: valp=%p bad magic=0x%lx seq=%lu\n",
                    idx, (void *)valp, (unsigned long)valp->magic,
                    (unsigned long)valp->seq);
        }

        /* writer side: publish our own new data */
        new = CRYPTO_zalloc(sizeof(*new), NULL, 0);
        new->magic = 0xBEEF;
        ossl_rcu_write_lock(rcu_lock);
        old = ossl_rcu_deref(&writer_ptr);
        new->seq = atomic_fetch_add(&global_seq, 1);
        ossl_rcu_assign_ptr(&writer_ptr, &new);
        ossl_rcu_write_unlock(rcu_lock);

        usleep(sleep_us);

        /* re-check the reference we grabbed above -- UAF if it was freed
         * while we still held the read lock on it */
        if (valp != NULL) {
            if (valp->magic != 0xF111 && valp->magic != 0xBEEF) {
                fprintf(stderr, "[victim %ld] UAF AFTER HOLD: valp=%p magic=0x%lx\n",
                        idx, (void *)valp, (unsigned long)valp->magic);
            }
        }
        ossl_rcu_read_unlock(rcu_lock);

        ossl_synchronize_rcu(rcu_lock);
        if (old != NULL) {
            old->magic = 0xDEAD0002;
            CRYPTO_free(old, NULL, 0);
        }
    }
    return NULL;
}

int main(void)
{
    pthread_t fillers[NUM_FILLERS];
    pthread_t victims[NUM_VICTIM_THREADS];
    int i;

    rcu_lock = ossl_rcu_lock_new(NUM_QPS, NULL);
    if (rcu_lock == NULL) {
        fprintf(stderr, "FAIL: could not create rcu lock\n");
        return 1;
    }

    for (i = 0; i < NUM_FILLERS; i++)
        pthread_create(&fillers[i], NULL, filler_writer_fn, NULL);
    for (i = 0; i < NUM_VICTIM_THREADS; i++)
        pthread_create(&victims[i], NULL, victim_thread_fn, (void *)(long)i);

    for (i = 0; i < NUM_VICTIM_THREADS; i++)
        pthread_join(victims[i], NULL);
    atomic_store(&stop_flag, 1);
    for (i = 0; i < NUM_FILLERS; i++)
        pthread_join(fillers[i], NULL);

    ossl_rcu_lock_free(rcu_lock);
    printf("DONE: no crash observed (global_seq=%lu)\n", (unsigned long)atomic_load(&global_seq));
    return 0;
}
