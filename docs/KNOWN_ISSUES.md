# Retained issues

The 265-case release retains the following six cases without rewriting frozen
tasks or transferring old results to changed snapshots. These are follow-up
repairs, not nine additional exclusions. The authoritative machine-readable
record is [`provenance/dataset_issues.json`](../provenance/dataset_issues.json).

| Case | Retained issue | Required next version |
|---|---|---|
| `sqlite/FORUM-8f384febcc9b` | Stored introduction is on `branch-3.53` | Reconstruct from matching mainline revision `73975a8f31f1ad6e2c93e4716108ed13944a3fdc`, then verify new tree/task identities |
| `curl/CVE-2026-9079` | CRLF context in `tests/data/test503` was lost; strict patch application fails | Serialize the patch without changing line-ending bytes and verify reconstruction |
| `curl/CVE-2025-0167` | Reconstructed `tests/data/test478` and `test479` lose CRLF bytes | Preserve exact fixture bytes and verify tree equality |
| `curl/CVE-2026-5545` | Reconstructed `tests/data/test338` loses CRLF bytes | Preserve exact fixture bytes and verify tree equality |
| `curl/GH-17830` | Reconstructed `tests/data/test4000` loses CRLF bytes | Preserve exact fixture bytes and verify tree equality |
| `curl/GH-19039` | Reconstructed `tests/data/test997` loses CRLF bytes | Preserve exact fixture bytes and verify tree equality |

Review materialization exports the declared upstream commit rather than replaying
the buggy patch. The CRLF problems therefore concern reconstruction fidelity
between the serialized review diff and declared tree; they still matter to
construction and replay claims.

Provisional security-impact notes remain for `ffmpeg/45daaf2caaa3`,
`ffmpeg/5021764413a1`, and `curl/GH-19039`. Other retained cases use adjudication,
source-based controls, feature-absent parents, partial-fix checks, or narrower
behavioral oracles. Do not relabel these as universal successful three-version
replays or established exploitation evidence.

Verification can construct a repaired tree by applying the companion patch to
the introducing parent. Historical review runs use the companion's recorded
upstream fixing revision. Preserve both identities and label the protocol used;
changing the companion snapshot requires a new evaluation version.

Bundling saved assets does not reproduce unavailable historical container images
or prove that every recorded command works on a new machine. Asset coverage and
missing references are recorded separately in `verification/`.

Frozen results are a filtered view of prior runs. Their current judge scores
target presence, including on companions. A negative companion verdict does
not measure whether the reviewer asserted the repaired target as a false alarm.
Failure, interruption, and unavailable evidence must remain visible rather than
being recoded as successful empty predictions.
