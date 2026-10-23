# Dataset card

## Intended task

SecPRBench evaluates whether a source-code reviewer identifies a specified
security failure in a real change. Each paired case has a buggy task and a
companion task. The reviewer receives a public review input and a source snapshot
without usable Git history. Private references, labels, verification records,
and upstream attribution are reserved for the evaluator.

The release contains 265 cases / 530 tasks across curl (26), FFmpeg (61), Firefox
(27), FreeType (15), OpenSSL (29), Redis (16), SQLite (33), V8 (44), and Wasmtime
(14). Its source is the latest 274-case ACL paper snapshot, not the earlier
CGSA-Bench dataset or SecPRBench's historical 160-case roster.

## Eligibility

The release follows the paper's concrete code-level security failure, plausible
trust or untrusted-input boundary, causally related fix, and diff-size criteria.
Documentation-only, test-only, dependency-update, build-metadata changes, and
unsupported security claims are outside scope. Each review diff is capped at
30 files and 2,000 added plus deleted lines. The fixing collection window is
January 1, 2025 inclusive through July 1, 2026 exclusive, using committer dates.

There is **no lower introduction-date bound**. All 36 previously flagged
pre-2021 introductions remain. Their committer dates range from July 18, 2002
to September 8, 2020. Removing the date cutoff does not imply exhaustive
historical collection or uniform historical buildability.

The release seeks traceable mainline attribution. One retained SQLite pair has
a known release-branch introduction requiring a newly versioned reconstruction;
it is disclosed as a retained issue, not claimed to comply already. Canonical
mainline fixing aliases are accepted when attributable. CVE assignment, an
exploit, and a sanitizer crash are not universal admission requirements.
Human-adjudicated, partial-fix, and feature-absent-parent cases retain their
case-specific evidence scope.

## Removed from the execution roster

| Case | Decision | Basis |
|---|---|---|
| `firefox/1950061` | Exclude | OpenH264 dependency-manifest update |
| `ffmpeg/268d0b6527cb` | Exclude | Scaler quality/correctness failure; unsupported security consequence |
| `ffmpeg/bd75fad85f37` | Exclude | Imported Vulkan-device initialization/configuration failure; unsupported security impact |
| `ffmpeg/c14b837dedad` | Exclude | Speex duration/audio correctness failure; unsupported security relevance |
| `ffmpeg/db7ff135744d` | Exclude | Filter configuration failure; unsupported security consequence |
| `openssl/GH-26346` | Exclude | Missing IV affects the `apps/speed.c` benchmark; no established security failure |
| `curl/GH-19377` | Exclude | Help-text formatting defect; evidence does not support the speculative dangerous behavior |
| `curl/GH-19269` | Exclude | Misleading download telemetry; oracle does not establish a security failure |
| `ffmpeg/TESTCASE-4015241140b49b26` | Hold | `ffmpeg -/version` crash lacks demonstrated untrusted-input boundary |

Both members of each removed case are absent from the active tasks, indexes,
roster, and filtered result cohort. The decision and source provenance remain
recorded in [`dataset_exclusions.json`](../provenance/dataset_exclusions.json).
The held case can be reconsidered if boundary evidence becomes available.

## Evidence and limitations

Tasks and copied evidence remain byte-identical to their frozen sources. New
sidecars describe selection and known defects. See
[`dataset_manifest.json`](../provenance/dataset_manifest.json) for integrity and
[`dataset_issues.json`](../provenance/dataset_issues.json) for retained caveats.
Six cases need artifact repairs, and additional cases have limited or
adjudicated security/replay evidence. These limitations are not new exclusions.

The corpus is a selected collection of public reports and attributed changes,
not a representative random sample of all vulnerabilities. Public disclosure,
project selection, construction success, historical toolchains, and model or
human adjudication can affect inclusion. Existing frozen judgments have not
received a completed independent human audit in this release. Findings about
other defects are not credited as detections of the case's reference target.

## Distribution

Upstream projects are identified in `configs/projects/*.yaml`; source snapshots
are obtained from their repositories when needed. Task JSON includes diffs and
may therefore contain upstream source fragments. Evidence and PoCs can contain
third-party material. Their original licenses and attribution apply; this
repository makes no blanket redistribution grant. See [license scope](../LICENSE_SCOPE.md).
