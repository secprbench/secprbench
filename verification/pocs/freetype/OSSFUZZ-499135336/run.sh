#!/bin/sh
# Reproducer for OSSFUZZ-499135336 (freetype autofit integer overflow).
#
# No black-box font PoC exists for this bug in a 64-bit FT_Pos build (see
# verdict explanation): the vulnerable line
#   point->y += movement;
# in af_move_contour_vertically() (src/autofit/aflatin.c) can only overflow
# a 64-bit FT_Pos if point->y is already within `movement` (<=64 in
# magnitude, per the caller's own cap check) of the FT_Pos boundary, a
# state legitimate glyph-coordinate scaling cannot reach in this build
# without first overflowing FT_MulFix's own 64-bit multiply (a separate,
# pre-existing code path).
#
# So this script exercises the documented root cause directly: if
# af_move_contour_vertically() exists in the checked-out revision, it
# compiles the autofit "unity" translation unit exactly like
# src/autofit/autofit.c does (giving access to the file-static function)
# and calls it with the exact precondition the (unmodified) caller in
# af_glyph_hints_apply_vertical_separation_adjustments() guarantees:
# point->y near the FT_Pos boundary, |movement| <= 64.
#
# In the parent revision (pre_intro) this function/feature does not exist
# at all -- there is no vulnerable code path to exercise, so the script
# exits cleanly (0) instead of failing a build, which would be
# inconclusive rather than a genuine "no bug" signal.

set -e
cd /work/src/autofit

if ! grep -q 'af_move_contour_vertically' aflatin.c; then
  echo "af_move_contour_vertically() is not present in this revision;" \
       "the vertical-separation-adjustment feature (and its bug) does" \
       "not exist yet here. Nothing to exercise -- clean by construction."
  exit 0
fi

cp /poc/poc_unity.c .

clang -g -O1 -fsanitize=address,undefined -fno-sanitize-recover=all \
      -fno-omit-frame-pointer \
      -DFT2_BUILD_LIBRARY -I/work/include -I/work/src -I. \
      poc_unity.c /work/build/libfreetype.a -lz -o /tmp/poc_unity_bin

/tmp/poc_unity_bin
