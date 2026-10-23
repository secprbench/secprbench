#define SQLITE_CORE 1
#include "sqlite3.h"
#include <stdio.h>

#ifdef HAVE_BASE64
extern int sqlite3_base_init(sqlite3 *db, char **pzErr, const void *pApi);
#endif

int main(void){
    sqlite3 *db;
    int rc = sqlite3_open(":memory:", &db);
    if(rc != SQLITE_OK){ fprintf(stderr, "open failed\n"); return 1; }
#ifdef HAVE_BASE64
    rc = sqlite3_base_init(db, 0, 0);
    if(rc != SQLITE_OK){ fprintf(stderr, "base64 init failed: %s\n", sqlite3_errmsg(db)); return 1; }
#endif
    sqlite3_stmt *st;
    const char *sql = "SELECT length(base64(zeroblob(600000000)));";
    rc = sqlite3_prepare_v2(db, sql, -1, &st, 0);
    if(rc != SQLITE_OK){
        printf("prepare rc=%d msg=%s\n", rc, sqlite3_errmsg(db));
        sqlite3_close(db);
        return 0;
    }
    rc = sqlite3_step(st);
    if(rc == SQLITE_ROW){
        printf("result length = %lld\n", (long long)sqlite3_column_int64(st,0));
    } else {
        printf("step rc=%d msg=%s\n", rc, sqlite3_errmsg(db));
    }
    sqlite3_finalize(st);
    sqlite3_close(db);
    return 0;
}
