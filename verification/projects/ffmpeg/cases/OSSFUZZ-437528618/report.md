# Verification report: pr_review_OSSFUZZ-437528618

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: NullPointerDereference
- **Intro commit**: `d9fed9df2a9e70c9375d3b2591db35c09303d369`
- **Intro parent**: `202a35ecdb44849953c61dc1fba9643c69b3d5e5`
- **Fix commit**: `a28e01a6c16430da689340d0af6eec094020b719`
- **Affected files**: ['libavformat/mov.c']

## PoC
- source: agent-generated (initial source: incomplete)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/ffmpeg/fdaf0a0e91b69169b9a6/attempts/01/pocs/ffmpeg/OSSFUZZ-437528618`
- input: `poc.mov` (155 bytes)
- run.sh: True

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- The single 'infe' entry makes mov_read_infe() call heif_add_stream(), which creates the sole AVStream and allocates a 1-element sc->sample_sizes/sc->chunk_offsets array for it (this is fc->streams[nb_streams-1]). The following top-level 'stsz' box is dispatched by mov_read_stsz() against that same (only) stream; because its declared 100-entry table is truncated to 0 actual bytes, ffio_read_size() fails and mov_read_stsz() executes av_freep(&sc->sample_sizes) then returns 0 (non-fatal). Later, mov_read_header()'s HEIF-finalization loop unconditionally executes `sc->sample_sizes[0] = item->extent_length;` for the item, dereferencing the now-NULL pointer. Running the identical command/input against all three builds: post_intro (d9fed9df2a9e) crashes on every run with AddressSanitizer "SEGV on unknown address 0x000000000000 ... WRITE memory access ... #0 mov_read_header /work/libavformat/mov.c:8856:34" via avformat_open_input -> ifile_open -> main (exit 134/SIGABRT) - this is exactly the labelled NullPointerDereference, matching the OSS-Fuzz report's "Crash Type: Null-dereference WRITE, Crash Address: 0x000000000000" with the identical stack root. pre_intro (202a35ecdb44) runs to full completion with exit 0 and no sanitizer activity whatsoever on the exact same input/command: its heif_add_stream() performs the array allocation, the sample_sizes[0]/chunk_offsets[0] write, and mov_build_index() all synchronously within the single call made while processing the 'meta' box, fully completing before the sibling 'stsz' box is ever reached, so there is no window in which the array can be freed before the write occurs; consequently the file demuxes and remuxes cleanly (exit 0). post_benign (companion fix applying a28e01a6c164) also runs to full completion with exit 0 and no sanitizer activity, because the fix removes the sc->sample_sizes/chunk_offsets heap array for HEIF items entirely, replacing it with scalar sc->sample_size/sc->stsz_sample_size fields that mov_read_stsz's free-on-truncated-read path cannot NULL out. This 3-way comparison (crash only in post_intro; fully clean, identical exit-0 success in both pre_intro and post_benign) using the exact same reproducer confirms both the introduction and the benign fix.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=202a35ecdb44  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=d660df8205ebeb358e1ebb35079dcf2e9429456dbc8e3010ba8cf1f221acdec2
  source_integrity=True
  output_tail:
    VERIFY_EXIT=0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=d9fed9df2a9e  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=d660df8205ebeb358e1ebb35079dcf2e9429456dbc8e3010ba8cf1f221acdec2
  source_integrity=True
  sanitizer:
    VERIFY_EXIT=134
    
    AddressSanitizer:DEADLYSIGNAL
    =================================================================
    ==9==ERROR: AddressSanitizer: SEGV on unknown address 0x000000000000 (pc 0x55bf4eb9763d bp 0x7ffd9fdbbe50 sp 0x7ffd9fdbba80 T0)
    ==9==The signal is caused by a WRITE memory access.
    ==9==Hint: address points to the zero page.
        #0 0x55bf4eb9763d in mov_read_header /work/libavformat/mov.c:8856:34
        #1 0x55bf4ea79c28 in avformat_open_input /work/libavformat/demux.c:316:20
        #2 0x55bf4e2e4489 in ifile_open /work/fftools/ffmpeg_demux.c:1452:11
        #3 0x55bf4e336d86 in open_files /work/fftools/ffmpeg_opt.c:1308:15
        #4 0x55bf4e336d86 in ffmpeg_parse_options /work/fftools/ffmpeg_opt.c:1348:11
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=202a35ecdb44  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=d660df8205ebeb358e1ebb35079dcf2e9429456dbc8e3010ba8cf1f221acdec2
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    VERIFY_EXIT=0
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
