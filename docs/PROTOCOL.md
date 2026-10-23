# Evaluation protocol and snapshot identities

The released cohort is frozen. Steps 1 to 5 below describe how it was built
and are recorded in the data and provenance files; the construction tooling is
not part of this repository. Steps 6 and 7 are what an evaluator runs.

1. Collect public candidate records and attributable fixing changes.
2. Establish the target causal security failure and trace an introduction.
3. Construct the buggy review change and a repaired companion change. Record
   reference evidence, commit identities, changed files, and exact task bytes.
4. Use the applicable replay or adjudication route to assess admission, recording
   what the evidence actually establishes. The routes are not interchangeable.
5. Freeze paired task/evidence hashes in a roster. This release applies the nine
   recorded removals to the latest 274-case roster without editing the retained
   task bytes or removing cases by age.
6. Materialize a history-blocked source tree and an allowlisted public review
   input. Run the scanner in the Docker containment boundary.
7. Judge successfully completed findings on the host with private target
   evidence, then report results over the complete assignment denominator.

## Distinct tree roles

| Role | Meaning |
|---|---|
| Introducing parent | Original tree preceding the introducing revision |
| Buggy review snapshot | Recorded introducing commit exported by the materializer |
| Composed repaired verification tree | Introducing parent plus the stored companion patch |
| Historical companion review snapshot | Recorded upstream fixing commit exported by the materializer |

The composed repaired tree and upstream fixing snapshot need not be identical.
This release preserves the historical review protocol so copied
results still describe the same reviewed revisions. Do not claim composed-tree
replay as execution evidence for a different upstream snapshot. A future change
to the reviewed companion tree needs a versioned protocol and new review/judge
results.

Frozen original evidence can contain absolute paths used by the original run.
These are provenance, not runtime configuration. Current roster paths are
relative to `data/`, runtime clone/work paths are configurable, and bundled asset
manifests provide local verification-file references.
