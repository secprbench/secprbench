#!/bin/sh
cd /work
if ./ffmpeg -filters 2>&1 | grep -q " vif "; then
  ./ffmpeg -f lavfi -i "color=size=4x4" -f lavfi -i "color=size=4x4" -frames:v 5 -lavfi vif -f null -
else
  echo "VIF_FILTER_NOT_PRESENT"
  exit 0
fi
