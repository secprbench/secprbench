import struct, sys

def ffalign(x, a):
    return (x + a - 1) // a * a

width = int(sys.argv[2])
height = int(sys.argv[3])
cw = ffalign(width, 4)
ch = ffalign(height, 4)
tex_size = cw * ch * 4  # tex_rat=1 due to RAW override

tag = b'6GCY'  # DXV_FMT_YCG6 little-endian bytes
hdr = tag + bytes([0x01, 0x00, 0x01, 0x00]) + struct.pack('<I', tex_size)
payload = b'\x00' * tex_size
data = hdr + payload
with open(sys.argv[1], 'wb') as f:
    f.write(data)
print(len(data), cw, ch, tex_size)
