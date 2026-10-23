#!/bin/bash
# Reproducer for OSSFUZZ-428055715 (osq.c U8P conversion 32-bit sample
# overflow). Builds libavcodec/osq.c with -fsanitize=signed-integer-overflow
# (this Docker target normally only enables ASan) and links it ahead of the
# cached libavcodec.a, together with /poc/poc.c which drives the OSQ decoder
# directly via avcodec_send_packet/avcodec_receive_frame using a hand-built
# extradata + bitstream. Works unmodified across pre_intro (no osq.c at all),
# post_intro (bug present) and post_benign (fix present).
set -e
cd /work

HAVE_OSQ=0
if grep -q "AV_CODEC_ID_OSQ" libavcodec/codec_id.h 2>/dev/null; then
    HAVE_OSQ=1
fi
echo "HAVE_OSQ=$HAVE_OSQ"

COMMON_INC="-I. -I./ -D_ISOC99_SOURCE -D_FILE_OFFSET_BITS=64 -D_LARGEFILE_SOURCE -D_POSIX_C_SOURCE=200112 -D_XOPEN_SOURCE=600 -DPIC -DZLIB_CONST -DHAVE_AV_CONFIG_H"

LINK_EXTRA_OBJ=""
UBSAN_FLAG=""
if [ "$HAVE_OSQ" = "1" ]; then
    UBSAN_FLAG="-fsanitize=signed-integer-overflow"
    clang $COMMON_INC -DBUILDING_avcodec -g -O1 -fsanitize=address $UBSAN_FLAG -fno-omit-frame-pointer -std=c11 -fPIC -pthread \
        -c -o /tmp/osq_ubsan.o libavcodec/osq.c
    LINK_EXTRA_OBJ="/tmp/osq_ubsan.o"
fi

clang -I. -I./ -DHAVE_AV_CONFIG_H -DHAVE_OSQ=$HAVE_OSQ -g -O1 -fsanitize=address -fno-omit-frame-pointer -std=c11 -fPIC -pthread \
    -c -o /tmp/poc.o /poc/poc.c

clang -Llibavcodec -Llibavdevice -Llibavfilter -Llibavformat -Llibavutil -Llibpostproc -Llibswscale -Llibswresample \
    -fsanitize=address $UBSAN_FLAG -Wl,--as-needed -Wl,-z,noexecstack -Wl,--warn-common -Qunused-arguments \
    -o /tmp/poc_bin /tmp/poc.o $LINK_EXTRA_OBJ \
    -lavdevice -lavfilter -lavformat -lavcodec -lpostproc -lswresample -lswscale -lavutil -lm -latomic -pthread -lz

/tmp/poc_bin
echo "PoC_EXIT=$?"
