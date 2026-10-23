CREATE TABLE t(x, CHECK ( x IS NULL OR length(x) > 0 ));
INSERT INTO t VALUES(zeroblob(200000));
UPDATE t SET x=x;
SELECT count(*) FROM t;
