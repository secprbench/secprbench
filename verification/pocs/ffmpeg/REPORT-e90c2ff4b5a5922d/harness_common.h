/* Common harness preamble for verifying OutOfBoundsRead in
 * parse_itut_t35_metadata() (libavcodec/libdav1d.c).
 *
 * This links against the real, unmodified target headers and static
 * libraries (libavcodec.a / libavutil.a) built from the exact commit under
 * test. Only the body of parse_itut_t35_metadata() itself is pasted in
 * verbatim (byte-identical, extracted via `sed` from /work/libavcodec/libdav1d.c
 * for that commit) because libdav1d.c as a whole cannot be compiled in this
 * environment: the build is configured with CONFIG_LIBDAV1D=0 (libdav1d
 * system library is not installed), so <dav1d/dav1d.h> and friends are
 * unavailable and the file is not part of the normal build at all.
 *
 * The struct layouts below (Dav1dITUTT35, minimal Libdav1dContext,
 * Dav1dPicture) match the real dav1d API fields that this specific function
 * actually touches (itut_t35->country_code / ->payload / ->payload_size,
 * dav1d->dovi). Nothing about the vulnerable logic itself is altered.
 */
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <stdlib.h>

#include "libavutil/internal.h"
#include "libavutil/avassert.h"
#include "libavutil/cpu.h"
#include "libavutil/film_grain_params.h"
#include "libavutil/hdr_dynamic_metadata.h"
#include "libavutil/mastering_display_metadata.h"
#include "libavutil/imgutils.h"
#include "libavutil/opt.h"

#include "libavcodec/atsc_a53.h"
#include "libavcodec/av1_parse.h"
#include "libavcodec/avcodec.h"
#include "libavcodec/bytestream.h"
#include "libavcodec/codec_internal.h"
#include "libavcodec/decode.h"
#include "libavcodec/dovi_rpu.h"
#include "libavcodec/internal.h"
#include "libavcodec/itut35.h"

typedef struct Dav1dITUTT35 {
    uint8_t country_code;
    uint8_t country_code_extension_byte;
    const uint8_t *payload;
    size_t payload_size;
} Dav1dITUTT35;

typedef struct Libdav1dContext {
    DOVIContext dovi;
} Libdav1dContext;

typedef struct Dav1dPicture {
    int dummy;
} Dav1dPicture;
