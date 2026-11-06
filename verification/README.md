# Verification bundle

Saved replay assets for the 265 cases: proof-of-concept inputs, replay records,
reports, and a per-case manifest. These files are evaluator evidence. Never
mount them into a reviewer container or give them to a scanner as task context.

```text
manifest.json                       per-case paths, hashes, and provenance
projects/<project>/cases/<case>/    saved replay JSON, reports, agent verdicts
pocs/<project>/<case>/              saved inputs, scripts, metadata, support files
```

```sh
python3.11 tools/bundle_verification.py --check
```

The check verifies the copied files and digests against `manifest.json` without
Docker, network access, or model calls. PoCs and copied third-party text keep
their original ownership and licenses; see [license scope](../LICENSE_SCOPE.md).
