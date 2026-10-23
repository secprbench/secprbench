#!/bin/sh
# Reproducer for REPORT-c911e0001115bbda (EXR DWA dc_w/dc_h floor-vs-ceil aliasing OOB read)
# Decodes the crafted DWA EXR (/poc/poc.exr) to raw gbrpf32le and prints the
# decoded value of pixel (40,24), which lies in the block whose DC coefficient
# index depends on dc_w/dc_h rounding (floor => aliases onto the wrong DC
# slot, ceil => reads the correct DC slot).
IN="${INPUT:-/poc/poc.exr}"
FFMPEG=ffmpeg
if [ -x /work/ffmpeg ]; then FFMPEG=/work/ffmpeg; fi
"$FFMPEG" -y -i "$IN" -f rawvideo -pix_fmt gbrpf32le /tmp/verify_out.raw 2>&1
python3 - << 'PY'
import struct
try:
    data = open('/tmp/verify_out.raw','rb').read()
    w,h = 42,30
    plane_size = w*h*4
    if len(data) < 3*plane_size:
        print("PIXEL_READ_FAILED insufficient_output_bytes=%d" % len(data))
    else:
        def getpix(p,x,y):
            off = p*plane_size + (y*w+x)*4
            return struct.unpack_from('<f', data, off)[0]
        x,y = 40,24
        g,b,r = getpix(0,x,y), getpix(1,x,y), getpix(2,x,y)
        print("PIXEL_G=%r PIXEL_B=%r PIXEL_R=%r" % (g,b,r))
except Exception as e:
    print("PIXEL_READ_FAILED", e)
PY
