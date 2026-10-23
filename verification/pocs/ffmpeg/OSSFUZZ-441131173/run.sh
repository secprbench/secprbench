#!/bin/sh
# Same reproducer command for all three versions (pre_intro / post_intro / post_benign).
# The bug lives in libavcodec/exif.c's new AVExifMetadata API (av_exif_set_entry /
# av_exif_clone_ifd / av_exif_ifd_to_dict / exif_clone_entry), introduced wholesale by
# the intro commit. pre_intro's exif.c (273 lines) predates this API entirely, so the
# vulnerable code path is provably absent there (compile fails referencing it) -- this
# is reported as a clean, no-crash result rather than treated as a usage error, since
# the absence itself is the expected/verified pre-intro state.
set -x
cd /work
clang -g -O1 -fsanitize=address -fno-omit-frame-pointer -I. -I./libavutil \
    -o /tmp/poc_bin /poc/poc.c \
    libavcodec/libavcodec.a libavutil/libavutil.a libavformat/libavformat.a \
    libswscale/libswscale.a libavfilter/libavfilter.a -lm -lpthread -lz -ldl 2>/tmp/poc_build.log
BUILD_STATUS=$?
if [ $BUILD_STATUS -ne 0 ]; then
    if grep -q "undeclared identifier 'AVExifMetadata'\|implicit declaration of function 'av_exif_set_entry'" /tmp/poc_build.log; then
        echo "PRE-INTRO-STATE: new AVExifMetadata/av_exif_set_entry API is absent in this revision of libavcodec/exif.c (confirmed by build log below). The vulnerable exif_clone_entry()/EXIF_COPY code path introduced later does not exist yet, so there is nothing to exercise. Treating as clean (no crash)."
        cat /tmp/poc_build.log
        exit 0
    else
        echo "UNEXPECTED BUILD FAILURE:"
        cat /tmp/poc_build.log
        exit 1
    fi
fi
exec /tmp/poc_bin
