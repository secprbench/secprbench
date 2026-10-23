#!/bin/bash
cd /tmp
rm -rf hlsout
mkdir hlsout
cd hlsout
cp /poc/sub.srt .

OUT="out%s%s%s%s%s%s%s%s.m3u8"

# First pass: create the HLS playlist + vtt segments normally (must succeed).
/work/ffmpeg -y -f lavfi -i "color=size=320x240:rate=1:duration=3" \
  -i sub.srt \
  -c:v mpeg4 -c:s webvtt \
  -f hls -hls_time 1 -hls_list_size 0 \
  "$OUT" > /tmp/hlsout/first.log 2>&1
if [ $? -ne 0 ]; then
  echo "FIRST PASS FAILED"
  cat /tmp/hlsout/first.log
  exit 2
fi

# Second pass: append_list mode triggers parse_playlist() which re-parses
# the existing playlist and, for subtitle segments, uses vtt_basename
# (derived from the output filename) as an snprintf format string.
# This exec'd command's exit status/signal is the script's own result.
exec /work/ffmpeg -y -f lavfi -i "color=size=320x240:rate=1:duration=3" \
  -i sub.srt \
  -c:v mpeg4 -c:s webvtt \
  -f hls -hls_time 1 -hls_list_size 0 -hls_flags append_list \
  "$OUT"
