#!/bin/bash
set -e
set -x
cd /work/src
CFLAGS="-pedantic -DREDIS_STATIC= -std=c99 -Wall -W -Wno-missing-field-initializers -O1 -g -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer -fcommon -I/work/src -I../deps/hiredis -I../deps/linenoise -I../deps/lua/src -I../deps/hdr_histogram"
cc $CFLAGS -c /poc/sha256_fixed.c -o /tmp/sha256_fixed.o

OBJS="adlist.o quicklist.o ae.o anet.o dict.o server.o sds.o zmalloc.o lzf_c.o lzf_d.o pqsort.o zipmap.o sha1.o ziplist.o release.o networking.o util.o object.o db.o replication.o rdb.o t_string.o t_list.o t_set.o t_zset.o t_hash.o config.o aof.o pubsub.o multi.o debug.o sort.o intset.o syncio.o cluster.o crc16.o endianconv.o slowlog.o scripting.o bio.o rio.o rand.o memtest.o crcspeed.o crc64.o bitops.o sentinel.o notify.o setproctitle.o blocked.o hyperloglog.o latency.o sparkline.o redis-check-rdb.o redis-check-aof.o geo.o lazyfree.o module.o evict.o expire.o geohash.o geohash_helper.o childinfo.o defrag.o siphash.o rax.o t_stream.o listpack.o localtime.o lolwut.o lolwut5.o lolwut6.o acl.o gopher.o tracking.o connection.o tls.o timeout.o setcpuaffinity.o monotonic.o mt19937-64.o"

cc -fsanitize=address,undefined -g -rdynamic -o /tmp/redis-server-fixed $OBJS /tmp/sha256_fixed.o ../deps/hiredis/libhiredis.a ../deps/lua/src/liblua.a -lm -ldl -pthread -lrt

echo "BUILD_FIXED_OK"
ls -la /tmp/redis-server-fixed
