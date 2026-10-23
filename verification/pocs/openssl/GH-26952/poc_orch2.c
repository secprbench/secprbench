/*
 * Reproducer v2 for GH-26952: multiple staggered "victim" writers each
 * paired with their own slow reader (holding real, non-NULL RCU-protected
 * data), interleaved with fast filler writers that wrap the small qp pool
 * around. This maximizes the chance that the writers_alloced bookkeeping
 * corruption caused by the buggy early retire-order signal lets a filler's
 * ossl_synchronize_rcu() return (and its caller free the data) while some
 * slow reader elsewhere is still actually dereferencing RCU-protected
 * memory -- a genuine, sanitizer-visible use-after-free.
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

#define NUM_QPS 4
#define NUM_FILLERS 6
#define NUM_VICTIM_ROUNDS 40
#define FILLER_TARGET_OPS 800000

static CRYPTO_RCU_LOCK *rcu_lock;
static uint64_t *writer_ptr = NULL;
static uint64_t global_ctr = 0;
static atomic_int go = 0;
static atomic_long filler_ops = 0;

static void *filler_writer_fn(void *arg)
{
    uint64_t *old, *new;

    while (!atomic_load(&go))
        ;
    while (atomic_load(&filler_ops) < FILLER_TARGET_OPS) {
        new = CRYPTO_zalloc(sizeof(uint64_t), NULL, 0);
        ossl_rcu_write_lock(rcu_lock);
        old = ossl_rcu_deref(&writer_ptr);
        *new = global_ctr++;
        ossl_rcu_assign_ptr(&writer_ptr, &new);
        ossl_rcu_write_unlock(rcu_lock);
        ossl_synchronize_rcu(rcu_lock);
        /* use the data right before freeing, so a UAF corrupts a value we
         * then write back out -- increases the odds ASAN/UBSan notices */
        if (old != NULL)
            *old = 0xdeadbeefUL;
        CRYPTO_free(old, NULL, 0);
        atomic_fetch_add(&filler_ops, 1);
    }
    return NULL;
}

struct victim_arg {
    int idx;
};

static void *victim_reader_pair_fn(void *arg)
{
    struct victim_arg *a = arg;
    uint64_t *old, *new, *valp;
    uint64_t val;
    int i;

    for (i = 0; i < NUM_VICTIM_ROUNDS; i++) {
        /* reader: grab a long-lived reference */
        ossl_rcu_read_lock(rcu_lock);
        valp = ossl_rcu_deref(&writer_ptr);
        val = (valp == NULL) ? 0 : *valp;

        /* writer: publish new data (old becomes what the reader above
         * might still be looking at, if it raced with an earlier update) */
        new = CRYPTO_zalloc(sizeof(uint64_t), NULL, 0);
        ossl_rcu_write_lock(rcu_lock);
        old = ossl_rcu_deref(&writer_ptr);
        *new = ++global_ctr;
        ossl_rcu_assign_ptr(&writer_ptr, &new);
        ossl_rcu_write_unlock(rcu_lock);

        /* hold the read reference for a while: this is the "slow reader"
         * for whichever generation `valp` belongs to */
        usleep(500 + (a->idx * 37) % 2000);
        if (valp != NULL) {
            /* read it again: UAF if it was freed under us */
            uint64_t val2 = *valp;
            if (val2 != val) {
                fprintf(stderr,
                        "[victim %d] CORRUPTION DETECTED: valp=%p read %llu then %llu\n",
                        a->idx, (void *)valp, (unsigned long long)val,
                        (unsigned long long)val2);
            }
        }
        ossl_rcu_read_unlock(rcu_lock);

        ossl_synchronize_rcu(rcu_lock);
        CRYPTO_free(old, NULL, 0);
    }
    return NULL;
}

int main(void)
{
    pthread_t fillers[NUM_FILLERS];
    pthread_t victims[8];
    struct victim_arg vargs[8];
    int i;

    rcu_lock = ossl_rcu_lock_new(NUM_QPS, NULL);
    if (rcu_lock == NULL) {
        fprintf(stderr, "FAIL: could not create rcu lock\n");
        return 1;
    }

    for (i = 0; i < NUM_FILLERS; i++)
        pthread_create(&fillers[i], NULL, filler_writer_fn, NULL);
    for (i = 0; i < 8; i++) {
        vargs[i].idx = i;
        pthread_create(&victims[i], NULL, victim_reader_pair_fn, &vargs[i]);
    }

    atomic_store(&go, 1);

    for (i = 0; i < 8; i++)
        pthread_join(victims[i], NULL);
    atomic_store(&filler_ops, FILLER_TARGET_OPS); /* let fillers wind down */
    for (i = 0; i < NUM_FILLERS; i++)
        pthread_join(fillers[i], NULL);

    ossl_rcu_lock_free(rcu_lock);
    printf("DONE: no crash observed (filler_ops=%ld)\n", (long)atomic_load(&filler_ops));
    return 0;
}
