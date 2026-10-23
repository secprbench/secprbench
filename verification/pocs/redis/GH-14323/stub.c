/* Minimal stand-ins for the jemalloc-provided hooks that src/defrag.c
 * expects under HAVE_DEFRAG. We force HAVE_DEFRAG on for a private
 * recompiled copy of the *unmodified* target defrag.c so the real
 * (buggy / fixed) activeDefragHExpiresOB logic executes, without
 * requiring the special redis-patched jemalloc to be built in this
 * ASAN container (ASAN forces MALLOC=libc upstream).
 *
 * je_get_defrag_hint always says "yes, move it" so our harness can
 * deterministically force activeDefragAlloc() to reallocate+free the
 * target kvobj, exactly like real jemalloc would signal for a
 * fragmented allocation.
 */
#include <stddef.h>
#include <stdlib.h>

int je_get_defrag_hint(void *ptr) {
    (void)ptr;
    return 1;
}

void *zmalloc_no_tcache(size_t size) {
    return malloc(size);
}

void zfree_no_tcache(void *ptr) {
    free(ptr);
}
