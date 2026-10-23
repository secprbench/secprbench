#!/bin/bash
# Reproducer for OSSFUZZ-461519938 (libswscale/output.c, yuv2gbrp16_full_X_c).
#
# The project's configured build here only enables ASan (no UBSan), and the
# labelled bug is a signed-integer-overflow (UBSan) issue with no usable
# existing PoC/corpus. This script:
#   1. Recompiles the single translation unit libswscale/output.c with
#      -fsanitize=undefined added (tracked source is NOT modified -- only
#      the compiler invocation changes) and relinks it into ffmpeg_g /
#      ffmpeg so the UBSan runtime is present.
#   2. Compiles /poc/poc_driver.c (added under /poc, never touching tracked
#      source), which #includes the unmodified libswscale/output.c and
#      calls the internal yuv2gbrp16_full_X_c() directly with crafted
#      filter taps/coefficients that reproduce the reported overflow shape.
#   3. Runs the resulting driver binary.
#
# Same script/inputs are used, unmodified, against pre_intro, post_intro
# and post_benign.
set -e
cd /work

CFLAGS_COMMON="-I. -I./ -D_ISOC99_SOURCE -D_FILE_OFFSET_BITS=64 -D_LARGEFILE_SOURCE -D_POSIX_C_SOURCE=200112 -D_XOPEN_SOURCE=600 -DPIC -DZLIB_CONST -g -O1 -fno-omit-frame-pointer -std=c11 -fPIC -pthread -Wno-parentheses -Wno-switch -fno-math-errno -fno-signed-zeros -mstack-alignment=16 -Qunused-arguments"

# Step 1: rebuild output.c with UBSan added, swap it into libswscale.a, and
# relink ffmpeg_g/ffmpeg, purely so the UBSan runtime is linked in. This
# does not change any tracked source file.
clang $CFLAGS_COMMON -DHAVE_AV_CONFIG_H -DBUILDING_swscale \
  -fsanitize=address -fsanitize=undefined -fno-sanitize-recover=undefined \
  -c -o libswscale/output.o libswscale/output.c
ar r libswscale/libswscale.a libswscale/output.o >/dev/null
touch fftools/ffmpeg.c
make -s ffmpeg_g >/tmp/relink.log 2>&1 || { echo "RELINK FAILED"; tail -80 /tmp/relink.log; exit 1; }
cp ffmpeg_g ffmpeg

# Step 2: compile the direct-call driver against the same (unmodified)
# libswscale/output.c, with the same UBSan flags.
clang $CFLAGS_COMMON -DHAVE_AV_CONFIG_H -DBUILDING_swscale \
  -fsanitize=address -fsanitize=undefined -fno-sanitize-recover=undefined \
  -o /tmp/poc_driver /poc/poc_driver.c \
  -Llibavutil -lavutil -lm -latomic -pthread

# Step 3: run it.
echo "=== running poc_driver against $(git -C /work rev-parse HEAD 2>/dev/null || echo unknown) ==="
/tmp/poc_driver
echo "poc_driver exit code: $?"
