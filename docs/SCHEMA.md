# Data contracts

## Host-only records

`data/roster.json` contains one `entries` element per case. Each entry identifies
`project`, `bug_id`, and `buggy`/`benign` objects with task `path` and `sha256`.
Paths resolve relative to `data/` for the documented run command. Task files
include `task_id`, `bug_id`, `task_type`, `commit_sha`, public PR text/diffs,
and private reference fields such as `ground_truth`.

The roster and exact task bytes are authoritative; the JSONL indexes are
convenience exports. The release validator checks agreement across the roster,
indexes, evidence, source hashes, and frozen result subset. Preserved historical
fields and absolute paths are provenance and are not reviewer-visible.

Private archival models in `secprbench/schema.py` preserve unknown fields so
imported evidence is not silently dropped. Hashes refer to original bytes, not
round-tripped Pydantic models or reformatted JSON. Selection metadata and known
issues live in `provenance/` sidecars.

## Reviewer input

`ReviewInput` rejects extra fields. Its allowlist is `files`, `full_diff`,
`commit_message`, `pr_title`, and `pr_description`. File records also reject
extra fields. Only the generated `input.json` and `brief.md` are mounted as public
task input. Known synthetic construction labels are scrubbed; genuine upstream
text remains available.

The host assigns an opaque 12-character hexadecimal run identifier. Both members
of a case receive different identifiers. Private bug IDs, labels, fixes, roster
metadata, and references must not be supplied to the scanner through paths,
prompts, or mounts. The host keeps the identity mapping separately.

## Predictions

The schema is
[`prediction.schema.json`](../secprbench/harnesses/prediction.schema.json):

```json
{
  "instance_id": "012345abcdef",
  "model": "scanner-version",
  "predictions": [
    {
      "title": "Description of the security failure",
      "message": "Explain the causal mechanism and security impact.",
      "file": "src/example.c",
      "start_line": 42,
      "severity": "high",
      "bug_type": "BufferOverflow",
      "confidence": 0.9
    }
  ]
}
```

The runtime additionally checks the assigned opaque ID, relative paths, and
changed-file scope. Findings outside changed files are dropped with accounting;
invalid output fails the review. An empty predictions array represents a
completed review that reported no findings. Missing output, process failure,
timeout, or unsuccessful model generation must not become an empty prediction.
See [harness details](HARNESS_CONTRACT.md).
