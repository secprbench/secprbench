# Reporting and frozen results

`artifacts/results/results_265_opus55_high.json` is a filtered subset of the
latest paper snapshot: retained case identities and their existing results are
copied, with provenance. The name describes the judge configuration; it does
not mean that only one reviewer model is included. Filtering performed no new
review, inference, or judgment.

`artifacts/results/summary_265.json` provides derived release statistics. The
offline release validator checks cohort identity and accounting. To generate
an additional report from the frozen snapshot without model calls:

```sh
secprbench report \
  --snapshot artifacts/results/results_265_opus55_high.json \
  --out .work/frozen-report
```

The command writes `baseline_derived.json` and `recall.md`, with all eight
current method labels and the complete assigned cohort. The inherited
`--paper-tables` option targets an earlier five-model manuscript layout and is
rejected for this newer snapshot schema. Use the current snapshot/summary and
default report rather than legacy LaTeX tables for this release.

For fresh evaluation output:

```sh
secprbench report --run-dir .work/example-run --out .work/example-report
```

The run report reads the saved assignment manifest, completed reviews, audits,
and judgments. Preserve assigned, scanned, judged, detected, empty, incomplete,
and failed counts. Interrupted or invalid runs stay in the assigned denominator.
Task detection and report counts measure different things.

Compare methods on the same case/task cohort and disclose any missing
assignments or completed-pair subset. Do not reuse the original 274-case paper
totals as 265-case results. Judge-positive companion counts describe asserted
target presence, not a separately validated false-alarm rate. See
[judge interpretation](JUDGE.md).

Frozen source records can retain original paths, timestamps, model identities,
and artifact hashes. They are provenance and must not be rewritten to suggest a
fresh run occurred in this checkout. Full raw model trajectories are not implied
by a compact result snapshot; inspect the bundled artifacts and manifests for
the actual coverage.
