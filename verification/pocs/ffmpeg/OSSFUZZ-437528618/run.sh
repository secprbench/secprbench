#!/bin/bash
./ffmpeg -nostdin -hide_banner -loglevel error -i /poc/poc.mov -c copy -f mpegts /tmp/verify_out.ts
