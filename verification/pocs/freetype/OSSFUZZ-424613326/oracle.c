#include <stdio.h>
#include <stdlib.h>

#include <ft2build.h>
#include FT_FREETYPE_H
#include FT_ERRORS_H
#include FT_TRUETYPE_TABLES_H

int main(int argc, char **argv) {
  if (argc != 2) return 2;
  FT_Library library = NULL;
  FT_Face face = NULL;
  FT_Error error = FT_Init_FreeType(&library);
  if (error) { fprintf(stderr, "init_error=%d\n", error); return 2; }
  error = FT_New_Face(library, argv[1], 1, &face);
  if (error) {
    fprintf(stderr, "open_error=%d\n", error);
    FT_Done_FreeType(library);
    return 2;
  }
  printf("face_index=%ld num_faces=%ld\n", face->face_index, face->num_faces);
  if (face->face_index != 1 || face->num_faces != 2) {
    FT_Done_Face(face);
    FT_Done_FreeType(library);
    return 2;
  }
  FT_ULong length = 0;
  error = FT_Load_Sfnt_Table(face, 1, 0, NULL, &length);
  printf("directory_length=%lu probe_error=%d\n", length, error);
  if (error == FT_Err_Table_Missing) {
    puts("ORACLE_RESULT=TAG1_UNSUPPORTED_NO_OOB");
    FT_Done_Face(face);
    FT_Done_FreeType(library);
    return 0;
  }
  if (error || length < 12 || length > 16 * 1024 * 1024) return 2;
  FT_Byte *bytes = malloc(length);
  if (!bytes) return 2;
  error = FT_Load_Sfnt_Table(face, 1, 0, bytes, &length);
  printf("directory_read_error=%d bytes=%lu\n", error, length);
  if (!error && length >= 12 && bytes[0] == 0 && bytes[1] == 1 &&
      bytes[2] == 0 && bytes[3] == 0)
    puts("ORACLE_RESULT=DIRECTORY_READ_NO_OOB");
  else
    error = 1;
  free(bytes);
  FT_Done_Face(face);
  FT_Done_FreeType(library);
  return error ? 2 : 0;
}
