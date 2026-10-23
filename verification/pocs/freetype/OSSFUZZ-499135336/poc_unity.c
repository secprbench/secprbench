/* Direct unit-level exercise of af_move_contour_vertically(), the
 * function whose unsafe `point->y += movement;` addition is the
 * documented root cause of OSSFUZZ-499135336 (fixed by using ADD_LONG).
 *
 * We build this by pulling in the autofit unity translation unit exactly
 * like src/autofit/autofit.c does, which gives us direct access to the
 * static af_move_contour_vertically() function within the same TU, then
 * drive it with a point whose y is deliberately placed within `movement`
 * of FT_Pos's positive boundary -- exactly the precondition described in
 * meta.json's root_cause (raw signed addition without an overflow-safe
 * helper).
 */
#define FT_MAKE_OPTION_SINGLE_OBJECT

#include "ft-hb.c"
#include "afadjust.c"
#include "afblue.c"
#include "afcjk.c"
#include "afdummy.c"
#include "afglobal.c"
#include "afhints.c"
#include "afindic.c"
#include "aflatin.c"
#include "afloader.c"
#include "afmodule.c"
#include "afranges.c"
#include "afshaper.c"

#include <stdio.h>
#include <limits.h>

int main( void )
{
  AF_PointRec  p;

  p.next = &p;
  p.prev = &p;
  p.y    = LONG_MAX - 30;   /* within `movement` of the FT_Pos boundary */

  fprintf( stderr, "before: y=%ld (LONG_MAX=%ld)\n", (long)p.y, (long)LONG_MAX );

  /* Same call shape as the TOP_CONTOUR_UP branch in
   * af_glyph_hints_apply_vertical_separation_adjustments(), where
   * `adjustment_amount` is guaranteed by that function's own cap check
   * to lie in (0, 64]. */
  af_move_contour_vertically( &p, 50 );

  fprintf( stderr, "after: y=%ld\n", (long)p.y );
  return 0;
}
