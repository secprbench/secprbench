/* Same-input FreeType allocator witness for the 2025 OT-SVG allocation cap. */
#include <ft2build.h>
#include FT_FREETYPE_H
#include FT_MODULE_H
#include FT_SYSTEM_H

#include <stdio.h>
#include <stdlib.h>

#define LARGE_REQUEST (64L * 1024L * 1024L)

static unsigned long large_alloc_count;
static long max_large_bytes;

static void *observed_alloc(FT_Memory memory, long size) {
  (void)memory;
  if (size >= LARGE_REQUEST) {
    ++large_alloc_count;
    if (size > max_large_bytes) max_large_bytes = size;
    return NULL;
  }
  return malloc(size > 0 ? (size_t)size : 1);
}

static void observed_free(FT_Memory memory, void *block) {
  (void)memory;
  free(block);
}

static void *observed_realloc(FT_Memory memory, long old_size, long new_size,
                              void *block) {
  (void)memory;
  (void)old_size;
  if (new_size >= LARGE_REQUEST) {
    ++large_alloc_count;
    if (new_size > max_large_bytes) max_large_bytes = new_size;
    return NULL;
  }
  return realloc(block, new_size > 0 ? (size_t)new_size : 1);
}

int main(int argc, char **argv) {
  if (argc != 2) return 2;
  struct FT_MemoryRec_ memory = {NULL, observed_alloc, observed_free,
                                 observed_realloc};
  FT_Library library = NULL;
  FT_Face face = NULL;
  FT_Error library_error = FT_New_Library(&memory, &library);
  FT_Error face_error = -1;
  FT_Error size_error = -1;
  FT_Error glyph_error = -1;
  long face_flags = 0;
  unsigned long glyph_format = 0;
  if (!library_error) {
    FT_Add_Default_Modules(library);
    face_error = FT_New_Face(library, argv[1], 0, &face);
    if (!face_error) {
      face_flags = face->face_flags;
      size_error = FT_Set_Pixel_Sizes(face, 0, 18);
      if (!size_error) {
        glyph_error = FT_Load_Glyph(face, 1, FT_LOAD_COLOR);
        if (!glyph_error) glyph_format = face->glyph->format;
      }
    }
  }
  printf("ORACLE library_error=%d face_error=%d size_error=%d "
         "glyph_error=%d face_flags=%ld glyph_format=%lu "
         "large_alloc_count=%lu max_large_bytes=%ld\n",
         library_error, face_error, size_error, glyph_error, face_flags,
         glyph_format, large_alloc_count, max_large_bytes);
  if (face) FT_Done_Face(face);
  if (library) FT_Done_Library(library);
  return library_error || face_error || size_error ? 2 : 0;
}
