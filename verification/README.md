# Verification bundle

This bundle preserves explicitly referenced replay assets for the filtered
265-case release. These files are evaluator/maintainer evidence and must not be
mounted into a reviewer container or supplied to a scanner as task context.

```text
manifest.json                       per-case coverage, paths, hashes, provenance
projects/<project>/cases/<case>/    saved replay JSON, reports, agent verdicts
pocs/<project>/<case>/              saved inputs, scripts, metadata, support files
```

The manifest includes all 265 retained cases. The copied bundle includes 127
replay records and 127 PoC directories with their available supporting outputs,
1,044 files and about 12.3 MB. For 113 PoC directories, the directory digest
matches the saved agent-execution digest; zero mismatch, and 14 lack a saved
digest comparison. The remaining 138 cases retain canonical data JSON evidence
but have no direct external replay reference followed by this bundler.

```sh
python3.11 tools/bundle_verification.py --check
```

This verifies copied bytes and digests without Docker, network access, or model
calls. The manifest records each asset's original relative location under a neutral
`/research-data/` placeholder next to its current path; machine-specific path
prefixes were replaced for publication and nothing else in the saved records was
edited.

The bundle does not assert that all cases have identical admission routes,
that every PoC has proven security impact, that all images can be downloaded,
or that any replay was rerun for this release. See
[verification guidance](../docs/VERIFICATION.md),
[known retained issues](../docs/KNOWN_ISSUES.md), and
[license scope](../LICENSE_SCOPE.md). PoCs and copied third-party text retain
their original ownership and applicable licenses; bundling is not a license grant.
