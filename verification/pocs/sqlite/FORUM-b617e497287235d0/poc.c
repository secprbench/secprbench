#include <stdio.h>
#include <stdlib.h>
#include "sqlite3.h"

static void preupdate_hook(void *pCtx, sqlite3 *db, int op,
                            const char *zDb, const char *zTbl,
                            sqlite3_int64 iKey1, sqlite3_int64 iKey2){
  sqlite3_value *pVal = 0;
  int rc;
  int i;
  /* Table t1 has 2 real columns (a rowid alias INTEGER PRIMARY KEY, and one
  ** normal column) plus one virtual (generated) column, so pTab->nCol==3
  ** and TF_HasVirtual is set. Call sqlite3_preupdate_old with a column
  ** index far outside [0, nCol) to force sqlite3TableColumnToStorage()
  ** to walk off the end of pTab->aCol[]. */
  for (i = 3; i < 3 + 4096; i += 1) {
    rc = sqlite3_preupdate_old(db, i, &pVal);
    (void)rc;
  }
  printf("preupdate_hook done op=%d\n", op);
}

int main(void){
  sqlite3 *db;
  char *errmsg = 0;
  int rc;

  rc = sqlite3_open(":memory:", &db);
  if( rc!=SQLITE_OK ){ fprintf(stderr, "open failed\n"); return 1; }

  rc = sqlite3_exec(db,
      "CREATE TABLE t1(a INTEGER PRIMARY KEY, b, c GENERATED ALWAYS AS (b+1));",
      0, 0, &errmsg);
  if( rc!=SQLITE_OK ){
    fprintf(stderr, "create failed: %s\n", errmsg?errmsg:"?");
    return 1;
  }
  rc = sqlite3_exec(db, "INSERT INTO t1(a,b) VALUES(1,10);", 0, 0, &errmsg);
  if( rc!=SQLITE_OK ){
    fprintf(stderr, "insert failed: %s\n", errmsg?errmsg:"?");
    return 1;
  }

  sqlite3_preupdate_hook(db, preupdate_hook, 0);

  rc = sqlite3_exec(db, "UPDATE t1 SET b=20 WHERE a=1;", 0, 0, &errmsg);
  if( rc!=SQLITE_OK ){
    fprintf(stderr, "update failed: %s\n", errmsg?errmsg:"?");
  }

  sqlite3_close(db);
  printf("done\n");
  return 0;
}
