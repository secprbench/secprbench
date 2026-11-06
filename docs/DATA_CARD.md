# Data card

## Task

SecPRBench evaluates whether a code reviewer identifies the security flaw in a
real change. Each case is the upstream change that introduced a vulnerability,
reviewed at the introducing commit. A paired companion task shows the repaired
change at the upstream fixing revision. The reviewer receives the diff, the
commit message, any upstream PR text, and a source snapshot without usable Git
history. Reference root causes, labels, and verification records stay with the
evaluator.

## Composition

| Project | Cases | Tasks |
|---|---:|---:|
| curl | 26 | 52 |
| FFmpeg | 61 | 122 |
| Firefox | 27 | 54 |
| FreeType | 15 | 30 |
| OpenSSL | 29 | 58 |
| Redis | 16 | 32 |
| SQLite | 33 | 66 |
| V8 | 44 | 88 |
| Wasmtime | 14 | 28 |
| **Total** | **265** | **530** |

## Selection

Each case has a concrete code-level security failure, a plausible trust boundary
or untrusted-input path, and a fix causally related to that failure.
Documentation-only, test-only, dependency-update, and build-metadata changes are
out of scope. Each review diff is capped at 30 files and 2,000 added plus
deleted lines.

The fixes were committed between January 1, 2025 and June 30, 2026. There is no
lower bound on the introduction date; the oldest introduction dates from 2002.
Of the 265 cases, 215 are confirmed by proof-of-concept replay, 2 by regression
tests, and 48 by human adjudication.

## Limitations

The cases are a selected collection of publicly reported vulnerabilities in nine
projects, not a random sample of all vulnerabilities. The judge credits only
findings that explain the reference root cause, so reports of other real
defects are not counted as detections.

## Distribution

Source snapshots are fetched from the upstream repositories listed in
`configs/projects/*.yaml`. Task diffs and PoCs can contain upstream material and
keep their original licenses. See [license scope](../LICENSE_SCOPE.md).
