#include <ft2build.h>
#include FT_FREETYPE_H
#include <stdio.h>

int main(int argc, char **argv) {
  if (argc < 2) { fprintf(stderr, "usage: %s font\n", argv[0]); return 2; }
  FT_Library lib;
  if (FT_Init_FreeType(&lib)) { fprintf(stderr, "init fail\n"); return 2; }
  FT_Face face;
  FT_Error err = FT_New_Face(lib, argv[1], 0, &face);
  if (err) { fprintf(stderr, "new_face fail: %d\n", err); return 2; }
  fprintf(stderr, "face ok, num_glyphs=%ld\n", (long)face->num_glyphs);

  err = FT_Set_Pixel_Sizes(face, 1008, 1008);
  if (err) { fprintf(stderr, "set_pixel_sizes fail: %d\n", err); return 2; }

  FT_UInt gid = FT_Get_Char_Index(face, 0x0169);
  fprintf(stderr, "gid for U+0169 = %u\n", gid);
  if (gid == 0) { fprintf(stderr, "no glyph mapped\n"); return 2; }

  err = FT_Load_Glyph(face, gid, FT_LOAD_FORCE_AUTOHINT | FT_LOAD_NO_BITMAP);
  fprintf(stderr, "load_glyph result: %d\n", err);

  FT_Done_Face(face);
  FT_Done_FreeType(lib);
  fprintf(stderr, "done, no crash\n");
  return 0;
}
