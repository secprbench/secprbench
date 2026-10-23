#!/bin/sh
set -e
cd /work
./ffmpeg -nostdin -hide_banner -loglevel error -i "${INPUT:-/poc/crash.mov}" -f null -
