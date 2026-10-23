#!/bin/bash
# PoC runner for GH-14323 (UseAfterFree in activeDefragHExpiresOB, src/defrag.c)
#
# This ASAN-instrumented redis build forces MALLOC=libc (see src/Makefile:
# `ifeq ($(SANITIZER),address) MALLOC=libc ...`), so the real jemalloc-based
# HAVE_DEFRAG code path (gated by `#if defined(USE_JEMALLOC) &&
# defined(JEMALLOC_FRAG_HINT)` in src/zmalloc.h) is compiled out of the
# shipped redis-server entirely -- activeDefragHExpiresOB does not even
# exist in that binary, and CONFIG SET activedefrag is rejected. So we build
# a small auxiliary harness that:
#   1. Recompiles a private copy of the *unmodified* src/defrag.c with
#      -DHAVE_DEFRAG, so the real (buggy / fixed, depending on version)
#      activeDefragHExpiresOB body is used -- not a reimplementation.
#   2. Supplies trivial stand-ins for the two jemalloc-only hooks it calls
#      (je_get_defrag_hint, zmalloc_no_tcache/zfree_no_tcache): functionally
#      equivalent malloc/free, with je_get_defrag_hint always returning 1 so
#      "this allocation should move" is forced deterministically instead of
#      depending on real jemalloc fragmentation heuristics (orthogonal to
#      this ordering bug).
#   3. Relinks these with all the target's other already-built, unmodified
#      object files, using `-Wl,--wrap=aeMain` so the stock server.c main()
#      performs its normal full startup (initServerConfig/initServer/
#      InitServerLast/loadDataFromDisk), and our code runs once that
#      completes (instead of the real event loop).
#   4. Creates a hash with a field TTL (HSET + HEXPIRE), which is enough to
#      register the hash kvobj in db->hexpires, then directly drives the
#      same ebScanDefrag()/activeDefragHExpiresOB() call that
#      defragStageHExpires() uses in production.
#
# On pre_intro, the entire per-item ebuckets-defrag mechanism
# (ebScanDefrag/ebDefragFunctions/activeDefragHExpiresOB) does not exist yet
# (pre_intro's src/ebuckets.h only has a scalar ebDefragFunction, no
# per-item support). harness.c detects this at compile time via
# HAS_EBSCANDEFRAG (probed below) and, when absent, runs only the setup
# commands and exits cleanly -- the absence of the API is itself the
# evidence that the bug was introduced together with this feature in the
# intro commit.
set -u
cd /work/src || exit 99

WORK=/tmp/poc_build
RUN=/tmp/rundir
rm -rf "$WORK" "$RUN"
mkdir -p "$WORK" "$RUN"

CFLAGS_COMMON="-pedantic -DREDIS_STATIC= -Wno-c11-extensions -std=gnu11 -Wall -W -Wno-missing-field-initializers -Werror=deprecated-declarations -Wstrict-prototypes -O1 -g -ggdb -g -O1 -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer -fcommon -I. -I../deps/hiredis -I../deps/linenoise -I../deps/lua/src -I../deps/hdr_histogram -I../deps/fpconv -I../deps/fast_float -DINCLUDE_VEC_SETS=1"

# Probe whether this revision has the per-item ebuckets-defrag API at all.
if grep -q "ebScanDefrag" ebuckets.h 2>/dev/null; then
    HAS_EBSCANDEFRAG=1
else
    HAS_EBSCANDEFRAG=0
fi
echo "=== HAS_EBSCANDEFRAG=$HAS_EBSCANDEFRAG ==="

# Work from a private copy of the *unmodified* defrag.c (tracked source is
# never written to). On some revisions, a mechanically-composed companion
# patch for this isolated task carries over one unrelated hunk from the same
# upstream multi-issue fix commit (a separate stream-consumer-group defrag
# fix referencing `nack->cgroup_ref_node`) whose struct member isn't present
# in this isolated snapshot's headers; that branch is normally dead code
# under this ASAN build (only reachable with -DHAVE_DEFRAG, which we are the
# first to actually compile), and is unrelated to the HFE/UAF bug under
# test, so we neutralize just that line in our private copy if present (a
# no-op on revisions that don't have it).
cp defrag.c "$WORK/defrag_copy.c"
sed -i "s/nack->cgroup_ref_node->value = ctx->cg;.*$/\/* harness: neutralized unrelated hunk (missing cgroup_ref_node member in this snapshot) *\//" "$WORK/defrag_copy.c"

cc $CFLAGS_COMMON -DHAVE_DEFRAG -o "$WORK/defrag_harness.o" -c "$WORK/defrag_copy.c" > "$WORK/defrag_cc.log" 2>&1
DEFRAG_CC_RC=$?
cc $CFLAGS_COMMON -o "$WORK/stub.o" -c /poc/stub.c > "$WORK/stub_cc.log" 2>&1
STUB_CC_RC=$?
cc $CFLAGS_COMMON -DHAS_EBSCANDEFRAG=$HAS_EBSCANDEFRAG -o "$WORK/harness.o" -c /poc/harness.c > "$WORK/harness_cc.log" 2>&1
HARNESS_CC_RC=$?

if [ $DEFRAG_CC_RC -ne 0 ] || [ $STUB_CC_RC -ne 0 ] || [ $HARNESS_CC_RC -ne 0 ]; then
    echo "=== HARNESS BUILD: COMPILE FAILED (defrag=$DEFRAG_CC_RC stub=$STUB_CC_RC harness=$HARNESS_CC_RC) ==="
    echo "--- defrag_cc.log ---"; cat "$WORK/defrag_cc.log"
    echo "--- stub_cc.log ---"; cat "$WORK/stub_cc.log"
    echo "--- harness_cc.log ---"; cat "$WORK/harness_cc.log"
    echo "HARNESS_RESULT=BUILD_FAILED"
    exit 10
fi

OBJS="threads_mngr.o adlist.o quicklist.o ae.o anet.o dict.o ebuckets.o eventnotifier.o iothread.o mstr.o kvstore.o server.o sds.o zmalloc.o lzf_c.o lzf_d.o pqsort.o zipmap.o sha1.o ziplist.o release.o networking.o util.o object.o db.o replication.o rdb.o t_string.o t_list.o t_set.o t_zset.o t_hash.o config.o aof.o pubsub.o multi.o debug.o sort.o intset.o syncio.o cluster.o cluster_legacy.o crc16.o endianconv.o slowlog.o eval.o bio.o rio.o rand.o memtest.o syscheck.o crcspeed.o crccombine.o crc64.o bitops.o sentinel.o notify.o setproctitle.o blocked.o hyperloglog.o latency.o sparkline.o redis-check-rdb.o redis-check-aof.o geo.o lazyfree.o module.o evict.o expire.o geohash.o geohash_helper.o childinfo.o siphash.o rax.o t_stream.o listpack.o localtime.o lolwut.o lolwut5.o lolwut6.o acl.o tracking.o socket.o tls.o sha256.o timeout.o setcpuaffinity.o monotonic.o mt19937-64.o resp_parser.o call_reply.o script_lua.o script.o functions.o function_lua.o commands.o strl.o connection.o unix.o logreqres.o hnsw.o vset.o"

cc -fsanitize=address,undefined -O1 -g -ggdb -rdynamic -Wl,--wrap=aeMain \
  -o "$WORK/redis-harness" \
  $OBJS "$WORK/defrag_harness.o" "$WORK/stub.o" "$WORK/harness.o" \
  ../deps/hiredis/libhiredis.a ../deps/lua/src/liblua.a ../deps/hdr_histogram/libhdrhistogram.a ../deps/fpconv/libfpconv.a ../deps/fast_float/libfast_float.a \
  -lm -lstdc++ -ldl -pthread -lrt > "$WORK/link.log" 2>&1
LINK_RC=$?

if [ $LINK_RC -ne 0 ]; then
    echo "=== HARNESS BUILD: LINK FAILED (rc=$LINK_RC) ==="
    echo "--- link.log ---"; cat "$WORK/link.log"
    echo "HARNESS_RESULT=LINK_FAILED"
    exit 11
fi

echo "=== HARNESS BUILD OK (HAS_EBSCANDEFRAG=$HAS_EBSCANDEFRAG), running PoC ==="
cd "$RUN" || exit 99
ASAN_OPTIONS=abort_on_error=0:detect_leaks=0:allocator_may_return_null=1 \
  timeout 30 "$WORK/redis-harness" --port 7799 --save '' --appendonly no --daemonize no --logfile '' > "$RUN/out.log" 2>&1
RUN_RC=$?
cat "$RUN/out.log"
echo "HARNESS_RUN_EXIT=$RUN_RC"
exit $RUN_RC
