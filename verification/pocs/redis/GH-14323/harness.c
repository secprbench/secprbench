/* PoC harness for GH-14323 (UseAfterFree in activeDefragHExpiresOB, src/defrag.c)
 *
 * We intercept the real redis-server's event loop entry point (aeMain) via
 * `-Wl,--wrap=aeMain`, so the *unmodified* server.c main() runs its normal
 * startup (initServerConfig/initServer/InitServerLast/loadDataFromDisk) and
 * leaves us with a fully valid `server` / `server.db[0]`. Instead of calling
 * the real event loop we run our test directly and exit.
 *
 * We create a hash key with a field TTL (HEXPIRE), which registers the hash
 * kvobj in db->hexpires. Where the target revision has the per-item
 * ebuckets-defrag API (HAS_EBSCANDEFRAG, passed in by run.sh after probing
 * src/ebuckets.h), we then directly drive the exact same
 * ebScanDefrag()/activeDefragHExpiresOB() defrag path that
 * defragStageHExpires() (src/defrag.c) uses, with activeDefragAlloc() wired
 * to our forced-"always move" je_get_defrag_hint() stub (see stub.c). This
 * reproduces, with the real unmodified target function, the use-after-free
 * where `keystr` (captured from the OLD kvobj before it is freed by
 * activeDefragAlloc) is dereferenced afterwards for the db->keys lookup.
 *
 * On revisions that predate this feature (pre_intro), HAS_EBSCANDEFRAG is 0:
 * the per-item ebuckets-defrag API does not exist at all there, so we only
 * run the setup commands and exit cleanly -- the function/API's absence is
 * itself the evidence that this bug was introduced together with the
 * feature in the intro commit (see run.sh / the recorded verdict).
 */
#include "server.h"
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <stdlib.h>

/* Non-static helper in aof.c, not exposed via server.h. */
struct client *createAOFClient(void);

#if HAS_EBSCANDEFRAG
/* Defined in defrag.c; not declared in server.h. */
void *activeDefragHExpiresOB(void *ptr, void *privdata);
#endif

static robj *mkstr(const char *s) {
    return createStringObject(s, strlen(s));
}

static void run_cmd(client *c, int argc, robj **argv) {
    struct redisCommand *cmd = lookupCommand(argv, argc);
    if (!cmd) {
        fprintf(stderr, "HARNESS: FAIL unknown command '%s'\n", (char *)argv[0]->ptr);
        exit(2);
    }
    c->argc = argc;
    c->argv = argv;
    c->argv_len = argc;
    c->cmd = c->lastcmd = cmd;
    cmd->proc(c);
    freeClientArgv(c); /* zfree(c->argv) -- argv MUST be heap allocated (zmalloc) */
}

#define MAXARGS 16
static void cmdf(client *c, int n, ...) {
    va_list ap;
    robj **argv = zmalloc(sizeof(robj *) * n);
    va_start(ap, n);
    for (int i = 0; i < n; i++) {
        const char *s = va_arg(ap, const char *);
        argv[i] = mkstr(s);
    }
    va_end(ap);
    run_cmd(c, n, argv);
}

void __wrap_aeMain(aeEventLoop *eventLoop) {
    (void)eventLoop;

    fprintf(stderr, "HARNESS: server fully initialized, running GH-14323 PoC\n");

    client *c = createAOFClient();

    /* A hash with one field that has a TTL -> registers the kvobj in
     * db->hexpires, exactly like the real "Active Defrag HFE" test does. */
    cmdf(c, 4, "HSET", "h1", "f1", "v");
    cmdf(c, 6, "HEXPIRE", "h1", "9999999", "FIELDS", "1", "f1");

    redisDb *db = &server.db[0];

    fprintf(stderr, "HARNESS: hexpires empty=%d\n", ebIsEmpty(db->hexpires));
    if (ebIsEmpty(db->hexpires)) {
        fprintf(stderr, "HARNESS: FAIL hash was not registered in db->hexpires\n");
        exit(3);
    }

#if HAS_EBSCANDEFRAG
    ebDefragFunctions eb_defragfns = {
        .defragAlloc = activeDefragAlloc,
        .defragItem = activeDefragHExpiresOB,
    };
    unsigned long cursor = 0;
    int rounds = 0;
    fprintf(stderr, "HARNESS: starting ebScanDefrag loop (should trigger UAF under ASAN)\n");
    while (ebScanDefrag(&db->hexpires, &hashExpireBucketsType, &cursor, &eb_defragfns, db)) {
        if (++rounds > 1000) break;
    }
    fprintf(stderr, "HARNESS: ebScanDefrag loop finished (rounds=%d) hits=%lld misses=%lld\n",
            rounds,
            (long long)server.stat_active_defrag_hits,
            (long long)server.stat_active_defrag_misses);

    /* Touch the (possibly moved) key again through the normal command path
     * to further stress any stale pointers that might have survived. */
    cmdf(c, 2, "HGETALL", "h1");
#else
    fprintf(stderr, "HARNESS: this revision has no per-item ebuckets-defrag API "
                    "(ebScanDefrag/activeDefragHExpiresOB absent) -- the HFE "
                    "active-defrag feature (and its bug) does not exist yet here; "
                    "skipping the defrag step and exiting cleanly.\n");
#endif

    fprintf(stderr, "HARNESS: PoC completed without a sanitizer trap\n");
    fflush(stderr);
    _exit(0);
}
