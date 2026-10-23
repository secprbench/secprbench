#!/bin/sh
# Reproducer for TESTCASE-03d3ae7878f783b7 (mov.c HEIF item_id search-or-allocate bug).
#
# /poc/heif_overwrite.mp4 is a crafted AVIF/HEIF-style MOV file with:
#   - an 'iloc' box declaring 1 item (item_id=100, capacity=1 slot) with a
#     real extent (offset=0x92/146, length=4) pointing into the trailing mdat,
#   - an 'iinf' box (entry_count=1, so capacity stays 1) containing two 'infe'
#     sub-entries: item_id=200 then item_id=300, both type 'jpeg'.
#
# Processing item 200 finds no matching slot but reuses the one free/matching
# slot found while scanning (the slot originally holding id=100), and creates
# a stream for it. Processing item 300 then scans the (now full, size-1)
# array, finds neither a matching id nor a free slot, and in the introduced
# bug silently falls through to reuse/overwrite the *last inspected* slot
# (the one now holding id=200) instead of aborting - orphaning the stream
# that was just created for id=200 (its HEIFItem/AVStream is never revisited
# by mov_parse_heif_items, so its sample table/index is never built).
#
# Oracle: after opening the file, check the trace log for whether the item
# with id 0xc8 (200) ended up with its own valid sample index entry.
cd /work || exit 1
./ffmpeg -v trace -i /poc/heif_overwrite.mp4 -f null - > /tmp/heif_log.txt 2>&1

if grep -q "error reading header" /tmp/heif_log.txt; then
    echo "RESULT: HEADER_REJECTED (file rejected as invalid)"
elif grep -q "AVIndex stream 0, sample 0, offset 92" /tmp/heif_log.txt; then
    echo "RESULT: STREAM0_INDEXED_OK (item 0xc8 properly retained its own extent/index)"
else
    echo "RESULT: STREAM0_ORPHANED_BUG (item 0xc8 stream opened but has no backing sample index; its HEIFItem slot was silently overwritten by a mismatched item id)"
fi
