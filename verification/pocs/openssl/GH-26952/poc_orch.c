/*
 * Orchestrated reproducer for GH-26952: forces one writer (the "victim")
 * to be stuck in ossl_synchronize_rcu()'s quiescence wait (because a
 * dedicated slow reader is holding its qp) while several "filler" writer
 * threads race through many back-to-back ossl_synchronize_rcu() calls,
 * cycling the circular qp_group index around until it wraps back onto the
 * victim's still-unretired qp. In the buggy ordering (retire-order signal
 * before the quiescence check) this wrap happens because the
 * writers_alloced bookkeeping is decremented by whichever writer retires,
 * not necessarily the victim, so capacity opens up for new allocations
 * while the victim's slot is still outstanding -- two independent RCU
 * "epochs" (the victim's and a filler's) end up mapped onto the same
 * physical qp, and both later call retire_qp() on it (double retirement /
 * corrupted writers_alloced accounting), which is the use-after-free
 * enabling defect from GH-26952. We keep the fillers running for a while
 * after the initial collision so that the corrupted bookkeeping has a
 * chance to cause a hard, sanitizer-visible failure (heap UAF / assert).
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
#define READER_HOLD_USEC 2000000
#define FILLER_TARGET_OPS 400000

static CRYPTO_RCU_LOCK *rcu_lock;
static uint64_t *writer_ptr = NULL;
static uint64_t global_ctr = 0;
static atomic_int reader_ready = 0;
static atomic_int victim_done = 0;
static atomic_long filler_ops = 0;
static struct timespec t_start;

static double elapsed(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (ts.tv_sec - t_start.tv_sec) + (ts.tv_nsec - t_start.tv_nsec) / 1e9;
}

static void *slow_reader_fn(void *arg)
{
    uint64_t *valp;
    uint64_t val_before, val_after;

    ossl_rcu_read_lock(rcu_lock);
    atomic_store(&reader_ready, 1);
    valp = ossl_rcu_deref(&writer_ptr);
    val_before = (valp == NULL) ? 0 : *valp;
    fprintf(stderr, "[reader t=%.3f] acquired, valp=%p val=%llu, sleeping %dms while holding\n",
            elapsed(), (void *)valp, (unsigned long long)val_before, READER_HOLD_USEC / 1000);
    usleep(READER_HOLD_USEC);
    val_after = (valp == NULL) ? 0 : *valp;
    fprintf(stderr, "[reader t=%.3f] waking, re-read val=%llu (was %llu) victim_done=%d\n",
            elapsed(), (unsigned long long)val_after, (unsigned long long)val_before,
            atomic_load(&victim_done));
    ossl_rcu_read_unlock(rcu_lock);
    return NULL;
}

static void *victim_writer_fn(void *arg)
{
    uint64_t *old, *new;

    while (!atomic_load(&reader_ready))
        ;
    new = CRYPTO_zalloc(sizeof(uint64_t), NULL, 0);
    ossl_rcu_write_lock(rcu_lock);
    old = ossl_rcu_deref(&writer_ptr);
    *new = global_ctr++;
    ossl_rcu_assign_ptr(&writer_ptr, &new);
    ossl_rcu_write_unlock(rcu_lock);
    fprintf(stderr, "[victim t=%.3f] entering synchronize_rcu, old=%p\n", elapsed(), (void *)old);
    ossl_synchronize_rcu(rcu_lock);
    fprintf(stderr, "[victim t=%.3f] synchronize_rcu RETURNED, freeing old=%p\n", elapsed(), (void *)old);
    CRYPTO_free(old, NULL, 0);
    atomic_store(&victim_done, 1);
    fprintf(stderr, "[victim t=%.3f] freed old\n", elapsed());
    return NULL;
}

static void *filler_writer_fn(void *arg)
{
    uint64_t *old, *new;

    while (!atomic_load(&reader_ready))
        ;
    while (atomic_load(&filler_ops) < FILLER_TARGET_OPS) {
        new = CRYPTO_zalloc(sizeof(uint64_t), NULL, 0);
        ossl_rcu_write_lock(rcu_lock);
        old = ossl_rcu_deref(&writer_ptr);
        *new = global_ctr++;
        ossl_rcu_assign_ptr(&writer_ptr, &new);
        ossl_rcu_write_unlock(rcu_lock);
        ossl_synchronize_rcu(rcu_lock);
        CRYPTO_free(old, NULL, 0);
        atomic_fetch_add(&filler_ops, 1);
    }
    return NULL;
}

int main(void)
{
    pthread_t reader, victim, fillers[NUM_FILLERS];
    int i;

    clock_gettime(CLOCK_MONOTONIC, &t_start);

    rcu_lock = ossl_rcu_lock_new(NUM_QPS, NULL);
    if (rcu_lock == NULL) {
        fprintf(stderr, "FAIL: could not create rcu lock\n");
        return 1;
    }

    pthread_create(&reader, NULL, slow_reader_fn, NULL);
    pthread_create(&victim, NULL, victim_writer_fn, NULL);
    for (i = 0; i < NUM_FILLERS; i++)
        pthread_create(&fillers[i], NULL, filler_writer_fn, NULL);

    pthread_join(victim, NULL);
    for (i = 0; i < NUM_FILLERS; i++)
        pthread_join(fillers[i], NULL);
    pthread_join(reader, NULL);

    ossl_rcu_lock_free(rcu_lock);
    printf("DONE: no crash observed (filler_ops=%ld)\n", (long)atomic_load(&filler_ops));
    return 0;
}
