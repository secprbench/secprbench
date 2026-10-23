# Changelog

## 0.2.0 — 2026-10-22, public release

- Published the 265-case / 530-task cohort with the evaluation harness only.
  The collection, construction, campaign, replay-verification, and triage
  tooling used to build the cohort is not included.
- Replaced machine-specific absolute paths in saved evidence, replay records,
  PoC metadata, and frozen result records with neutral placeholders. Task bytes
  and their hashes are unchanged; rebound evidence entries are marked
  `host_paths_redacted` in the dataset manifest.
- Removed packaging-host records (local image inventory, import receipts) and
  historical workspace documentation.

## 0.1.0 — 2026-10-10, prepublication release

- Selected 265 cases / 530 tasks from the 274-case paper snapshot by excluding
  eight cases and holding one case for security-boundary evidence.
- Retained all pre-2021 introductions; this release has no introduction-date
  lower bound.
- Preserved original task and evidence bytes, recorded provenance and retained
  issues, and provided a paired roster plus project JSONL indexes.
- Included the filtered frozen-result cohort with separate derived statistics;
  no new scanner or judge runs were performed for that filtering.
- Added offline release checks, portable runtime configuration, documentation,
  a scanner contract example, and continuous-integration checks.
