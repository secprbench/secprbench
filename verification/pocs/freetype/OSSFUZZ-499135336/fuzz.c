#include <ft2build.h>
#include FT_FREETYPE_H
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
  if (size < 16 || size > 200000) return 0;

  FT_Library lib;
  if (FT_Init_FreeType(&lib) != 0) return 0;

  FT_Face face;
  if (FT_New_Memory_Face(lib, data, (FT_Long)size, 0, &face) != 0) {
    FT_Done_FreeType(lib);
    return 0;
  }

  FT_Long n = face->num_glyphs;
  if (n > 40) n = 40;

  static const int sizes[] = { 1, 2, 3, 4, 6, 8, 10, 12, 16, 24, 32, 48, 64, 96, 128, 200, 400, 800, 1600, 3200, 6400, 12800, 25600, 51200, 65500 };
  for (unsigned s = 0; s < sizeof(sizes)/sizeof(sizes[0]); s++) {
    if (FT_Set_Pixel_Sizes(face, 0, sizes[s]) != 0) continue;
    for (FT_Long g = 0; g < n; g++) {
      FT_Load_Glyph(face, (FT_UInt)g, FT_LOAD_FORCE_AUTOHINT | FT_LOAD_NO_BITMAP);
    }
  }

  FT_Done_Face(face);
  FT_Done_FreeType(lib);
  return 0;
}
