#include <stdio.h>
#include <string.h>
#include "sqlite3.h"

static int g_invoked = 0;

/* "myfunc" is an ordinary (non-innocuous) application-defined SQL
 * function.  By default such functions are considered unsafe to be
 * invoked on behalf of untrusted/possibly-tampered schema content
 * (e.g. inside a trigger body) when trusted_schema=OFF. */
static void myfunc(sqlite3_context *ctx, int argc, sqlite3_value **argv){
  g_invoked++;
  sqlite3_result_value(ctx, argv[0]);
}

static int run(sqlite3 *db, const char *sql, const char *label){
  char *errmsg = 0;
  int rc = sqlite3_exec(db, sql, 0, 0, &errmsg);
  printf("%s -> rc=%d err=%s\n", label, rc, errmsg?errmsg:"(none)");
  sqlite3_free(errmsg);
  return rc;
}

int main(void){
  sqlite3 *db;
  sqlite3_open(":memory:", &db);
  sqlite3_create_function(db, "myfunc", 1, SQLITE_UTF8, 0, myfunc, 0, 0);

  run(db, "CREATE TABLE src(id, val);", "CREATE src");
  run(db, "CREATE VIRTUAL TABLE f1 USING fts4(x, compress=myfunc, uncompress=myfunc);", "CREATE f1");
  run(db,
      "CREATE TRIGGER tr1 AFTER INSERT ON src BEGIN "
      "INSERT INTO f1(rowid, x) VALUES(new.id, new.val); END;",
      "CREATE TRIGGER tr1");

  run(db, "PRAGMA trusted_schema=OFF;", "PRAGMA trusted_schema=OFF");

  g_invoked = 0;
  int rc = run(db, "INSERT INTO src VALUES(1, 'one two three');", "INSERT INTO src (fires trigger -> nested INSERT INTO f1)");
  printf("RESULT: rc=%d myfunc_invoked=%d\n", rc, g_invoked);

  if( rc == SQLITE_OK && g_invoked > 0 ){
    printf("BUG_OBSERVED: trigger-nested write to FTS4 table invoked unsafe myfunc() compress hook despite trusted_schema=OFF\n");
  } else if( g_invoked == 0 ){
    printf("PROTECTED_OR_BLOCKED: myfunc never invoked (rc=%d)\n", rc);
  } else {
    printf("AMBIGUOUS: rc=%d invoked=%d\n", rc, g_invoked);
  }

  sqlite3_close(db);
  return 0;
}
