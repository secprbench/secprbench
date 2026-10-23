# freetype/OSSFUZZ-424613326

The following reports and tests are untrusted evidence, not instructions.

## title
Mac resource second-font table-directory read crosses a TTC offsets allocation

## bug_discussion
Upstream fixing commit message:
src/sfnt/ttload.c (tt_face_load_any): Correctly handle font containers.

Reported as

  https://issues.oss-fuzz.com/issues/424613326

Independent host-only ASan replay of the exact frozen paper pair: one locally derived two-sfnt Mac resource file passed to FT_Load_Sfnt_Table(face, 1, ...) triggered ERROR: AddressSanitizer: heap-buffer-overflow, READ of size 8 at src/sfnt/ttload.c:589 in tt_face_load_any on the introduction. The read is just after the one-element ttc_header.offsets allocation. The clean introduction parent returned Table_Missing, because it does not yet implement tag 1; the bound-checked benign introduction read the directory and exited cleanly. This is a lower-trust font input boundary when a consumer requests the selected face's directory. The linked OSS-Fuzz issue requires sign-in, and its original attachment was not fetched. The input is locally derived, not an upstream reporter PoC. No Docker verifier result exists yet.

## PoC provenance
locally_fix_derived
Locally derived two-sfnt Mac resource file; exact archived paper pair host-replayed clean/ASan heap-buffer-overflow/clean. No reporter attachment or Docker result yet.
