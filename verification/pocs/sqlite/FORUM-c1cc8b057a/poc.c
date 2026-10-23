#include "sqlite3.h"
#include <stdio.h>
int main() {
    sqlite3 *db;
    sqlite3_open(":memory:", &db);
    sqlite3_exec(db, "CREATE TABLE t(a,b,c)", 0, 0, 0);
    sqlite3_exec(db, "CREATE INDEX i ON t(a,b,c)", 0, 0, 0);
    sqlite3_exec(db, "SELECT * FROM t ORDER BY a,b,c", 0, 0, 0);
    sqlite3_close(db);
    return 0;
}
