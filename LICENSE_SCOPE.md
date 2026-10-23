# License scope and provenance

This repository does not grant a new blanket
license for the current SecPRBench code, dataset, annotations, or PoC bundle.
The imported SecPRBench source did not provide a top-level license grant.

The earlier CGSA-Bench repository grants MIT for its benchmark tooling,
metadata, and schemas, and separately describes CC BY 4.0 for its per-bug
ground-truth annotations. Its exact original notice is preserved in
[`licenses/cgsa-bench-LICENSE.txt`](licenses/cgsa-bench-LICENSE.txt). Those grants
apply to material actually inherited from that repository within the stated
scope. They do not establish ownership or permission for newly collected
third-party reports, later SecPRBench code, or external PoCs.

The vendored defending skill retains its adjacent
[`LICENSE.txt`](secprbench/harnesses/defending/skill/LICENSE.txt), source
attribution, and upstream license. All other third-party dependencies retain
their own licenses.

Upstream task diffs and any source snippets retain the relevant project's
licenses. Copied advisories, issue text, saved logs, and PoCs retain their
original ownership and applicable licenses. A source URL or available file
does not by itself establish redistribution permission. Verification asset
manifests record provenance and coverage, not a licensing determination.

Before public publication, confirm the grant for author-owned code and
annotations, preserve applicable upstream notices, and decide whether each
third-party artifact can be distributed or should instead be retrieved by a
documented, checksummed download. Record that decision per artifact class.
