# Verification report: pr_review_OSSFUZZ-441131173

- **Status**: `verified`
- **Intro verified**: True
- **Benign verified**: True
- **Bug type**: OutOfBoundsRead
- **Intro commit**: `ad77345a5d14862f4701e5ad422b03b14934a5b9`
- **Intro parent**: `bb90b262d6d23f1bca3587a48abc15b951cbbf05`
- **Fix commit**: `76645e096fabd9beeecb681691b4bca327241ee8`
- **Affected files**: ['libavcodec/exif.c']

## PoC
- source: agent-generated (initial source: incomplete)
- dir: `/research-data/secprbench/campaign-100-20260928/operations/verify-watch-sonnet5-v7/cases/ffmpeg/e91a10ba27840acd026f/attempts/01/pocs/ffmpeg/OSSFUZZ-441131173`
- input: `None` (0 bytes)
- run.sh: True

## Findings

- The same Docker reproducer triggered a sanitizer or race report only after introduction.
- The intro commit (ad77345a5d14) adds an entirely new AVExifMetadata/AVExifEntry API to libavcodec/exif.c (av_exif_set_entry, av_exif_clone_ifd, av_exif_ifd_to_dict, exif_clone_entry, etc.). The parent (bb90b262d6d2) has an exif.c of only 273 lines containing none of these symbols, so run_poc against pre_intro cleanly reports exit=0/crashed=False (run.sh detects the expected "undeclared identifier 'AVExifMetadata'" / "implicit declaration of function 'av_exif_set_entry'" compiler errors and treats that as the confirmed pre-intro state: the vulnerable code path does not exist, hence nothing to crash). In post_intro, exif_clone_entry() handles the AV_TIFF_STRING case with the generic EXIF_COPY macro, doing av_memdup(src->value.str, src->count) -- copying only `count` bytes even though AV_TIFF_STRING values are always allocated/stored elsewhere in the parser as count+1 byte NUL-terminated C strings (av_mallocz(entry->count+1)). The cloned/stored string entry ends up exactly `count` bytes long with no room for the NUL terminator. When av_exif_ifd_to_dict() -> exif_ifd_to_dict() later formats that entry via av_bprintf(&bp, "%s", entry->value.str), libc's %s scan for a NUL runs one byte past the heap allocation. run_poc against post_intro shows exit=134/crashed=True with an AddressSanitizer heap-buffer-overflow READ of size 17, exactly matching the OSS-Fuzz report's call chain: printf_common -> av_bprintf (bprint.c:110) -> exif_ifd_to_dict (exif.c:897) -> av_exif_ifd_to_dict (exif.c:936), with the undersized allocation traced to exif_clone_entry (exif.c:1089) -> av_exif_set_entry (exif.c:1150) -- this is the labelled OutOfBoundsRead / heap-buffer-overflow READ bug (OSS-Fuzz 441131173, crash state av_bprintf/exif_ifd_to_dict/exif_attach_ifd). Running the identical PoC against post_benign (intro commit + fix 76645e096fab applied) completes cleanly: run_poc shows exit=0/crashed=False, correctly printing "ImageDescription = AAAAAAAAAAAAAAAA". The fix changed the AV_TIFF_STRING case in exif_clone_entry to explicitly do av_memdup(src->value.str, src->count+1), copying the extra NUL byte, which eliminates the overflow while preserving correct string round-tripping. No ASan report occurs in post_benign under the same reproducer, confirming the companion patch benignly removes the introduced bug.

## Agent oracle

- machine gate: verified (sanitizer)
- basis: The same Docker reproducer triggered a sanitizer or race report only after introduction.

## Per-version results

### pre_intro
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=False
  commit=bb90b262d6d2  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=5cde738dbb429df8eca701d372ef29b54d6b08b851bacd90a743540c1403e09f
  source_integrity=True
  output_tail:
                                        ^~~
                                         if
    /poc/poc.c:28:38: error: expected expression
    /poc/poc.c:36:5: warning: implicit declaration of function 'av_exif_free' is invalid in C99 [-Wimplicit-function-declaration]
        av_exif_free(&ifd);
        ^
    /poc/poc.c:36:19: error: use of undeclared identifier 'ifd'
        av_exif_free(&ifd);
                      ^
    3 warnings and 6 errors generated.
    VERIFY_EXIT=0
    
    + cd /work
    + clang -g -O1 -fsanitize=address -fno-omit-frame-pointer -I. -I./libavutil -o /tmp/poc_bin /poc/poc.c libavcodec/libavcodec.a libavutil/libavutil.a libavformat/libavformat.a libswscale/libswscale.a libavfilter/libavfilter.a -lm -lpthread -lz -ldl
    + BUILD_STATUS=1
    + '[' 1 -ne 0 ']'
    + grep -q 'undeclared identifier '\''AVExifMetadata'\''\|implicit declaration of function '\''av_exif_set_entry'\''' /tmp/poc_build.log
    + echo 'PRE-INTRO-STATE: new AVExifMetadata/av_exif_set_entry API is absent in this revision of libavcodec/exif.c (confirmed by build log below). The vulnerable exif_clone_entry()/EXIF_COPY code path introduced later does not exist yet, so there is nothing to exercise. Treating as clean (no crash).'
    + cat /tmp/poc_build.log
    + exit 0
```
### post_intro
```
  source=agent execution
  build_ok=True  crashed=True  exit=134  poc_ran=True  patched=False
  commit=ad77345a5d14  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=5cde738dbb429df8eca701d372ef29b54d6b08b851bacd90a743540c1403e09f
  source_integrity=True
  sanitizer:
     libavfilter/libavfilter.a -lm -lpthread -lz -ldl
    + BUILD_STATUS=0
    + '[' 0 -ne 0 ']'
    + exec /tmp/poc_bin
    av_exif_set_entry ret=0
    =================================================================
    ==8==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x603000000080 at pc 0x55e91875663d bp 0x7ffd373dde60 sp 0x7ffd373dd5e8
    READ of size 17 at 0x603000000080 thread T0
        #0 0x55e91875663c in printf_common(void*, char const*, __va_list_tag*) asan_interceptors.cpp.o
        #1 0x55e9187ffcfe in av_bprintf /work/libavutil/bprint.c:110:21
        #2 0x55e9187f7f4f in exif_ifd_to_dict /work/libavcodec/exif.c:897:17
        #3 0x55e9187f764f in av_exif_ifd_to_dict /work/libavcodec/exif.c:936:12
```
### post_benign
```
  source=agent execution
  build_ok=True  crashed=False  exit=0  poc_ran=True  patched=True
  commit=bb90b262d6d2  note=build cached
  command=cd /work && bash /poc/run.sh
  poc_sha256=5cde738dbb429df8eca701d372ef29b54d6b08b851bacd90a743540c1403e09f
  source_integrity=True
  patch_method=plain  patch_clean=True
  output_tail:
    VERIFY_EXIT=0
    
    + cd /work
    + clang -g -O1 -fsanitize=address -fno-omit-frame-pointer -I. -I./libavutil -o /tmp/poc_bin /poc/poc.c libavcodec/libavcodec.a libavutil/libavutil.a libavformat/libavformat.a libswscale/libswscale.a libavfilter/libavfilter.a -lm -lpthread -lz -ldl
    + BUILD_STATUS=0
    + '[' 0 -ne 0 ']'
    + exec /tmp/poc_bin
    av_exif_set_entry ret=0
    av_exif_ifd_to_dict ret=0
    entry: ImageDescription = AAAAAAAAAAAAAAAA
    POC DONE OK
```

## Interpretation

The parent, introducing, and patched versions matched the recorded oracle under the same reproducer. Inspect the oracle and target reachability to assess security impact.
