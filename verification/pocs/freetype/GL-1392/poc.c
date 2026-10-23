#include <stdio.h>
#include <stdlib.h>

#include <ft2build.h>
#include FT_FREETYPE_H

int
main( int argc, char **argv )
{
  FT_Library   library;
  FT_Face      face;
  FT_Vector    kerning;
  FILE*        fp;
  long         size;
  FT_Byte*     buf;
  const char*  path = argc > 1 ? argv[1] : "crafted.ttf";

  fp = fopen( path, "rb" );
  if ( !fp ) { fprintf(stderr, "cannot open %s\n", path); return 2; }
  fseek( fp, 0, SEEK_END );
  size = ftell( fp );
  rewind( fp );
  buf = (FT_Byte*)malloc( (size_t)size );
  fread( buf, 1, (size_t)size, fp );
  fclose( fp );

  if ( FT_Init_FreeType( &library ) ) { fprintf(stderr,"init fail\n"); return 2; }
  if ( FT_New_Memory_Face( library, buf, size, 0, &face ) ) {
    fprintf(stderr, "New_Memory_Face failed\n");
    return 3;
  }
  (void)FT_Set_Char_Size( face, 0, 16 * 64, 72, 72 );
  FT_Get_Kerning( face, 3, 1, FT_KERNING_DEFAULT, &kerning );
  printf("kerning.x=%ld kerning.y=%ld\n", (long)kerning.x, (long)kerning.y);
  FT_Done_Face( face );
  FT_Done_FreeType( library );
  free( buf );
  return 0;
}
