# Verification evidence and replay

All 265 retained cases carry canonical verification or adjudication information
in the frozen data. The additional `verification/` bundle follows explicit file
references from those records; it does not silently search for newer evidence
and replace the frozen claims.

The bundle contains 127 referenced historical replay records and
127 corresponding PoC directories, plus available reports and agent verdicts:
1,044 files totaling about 12.3 MB. Of the 127 PoC directories, 113 match saved
agent-execution digests, none mismatch, and 14 lack that digest comparison.
The other 138 cases have canonical JSON evidence but no direct external replay
reference followed by this bundler. These counts describe asset coverage, not
127 newly reproduced cases or failure of the other 138.

```sh
python3.11 tools/bundle_verification.py --check
```

The command checks the copied assets and directory digests against
[`verification/manifest.json`](../verification/manifest.json). Machine-specific
source paths were replaced by neutral `/research-data/` placeholders. Local asset paths work within this repository.
See the [bundle README](../verification/README.md) for layout and coverage.

## How cases were verified

Admission used a three-version replay where a portable reproducer existed: the
introducing parent, the introducing tree, and the parent plus the stored
companion patch were built and the same proof of concept was executed on all
three in Docker without network access. A deterministic clean, crash, clean
outcome is one admission route. Partial fixes, parents that predate a feature,
target-specific behavioral oracles, and human adjudication carry their recorded
interpretation. A generic nonzero exit, out-of-memory kill, timeout, or parser
error does not establish a vulnerability, and a successful replay establishes
the reproduced behavior, not its security impact or exploitability.

PoCs live under `verification/pocs/<project>/<bug_id>/`, with inputs, an optional
`run.sh`, and `meta.json`. Project build recipes are the `verify:` sections of
`configs/projects/*.yaml`. The replay driver itself is part of the benchmark
construction tooling and is not included in this evaluation repository; the
saved records under `verification/projects/` are the evidence it produced.

## Limits of the bundled evidence

No historical vulnerability build or PoC replay was rerun for packaging.
Saved reports, digest checks, and copied files do not prove portable execution.

Historical verification images were local to the authors' hosts and are not
distributed; replaying a case requires rebuilding the project at the recorded
revisions with the recipes in `configs/projects/*.yaml`.

The reviewed historical companion and composed repaired verification tree can
differ; see [snapshot identities](PROTOCOL.md). The six retained artifact issues
and narrower case-specific evidence remain in [known issues](KNOWN_ISSUES.md).
New repairs or replay results must create versioned sidecars/artifacts and keep
old evidence available rather than overwrite it.
