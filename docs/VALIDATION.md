# Validation

Checks on 2026-10-22 for the public release passed: **178 tests passed, 9
skipped, and 10 external/live tests deselected** in a clean virtual environment
with the test extra installed. Both integrity validators, lint, the scanner
example, and the frozen-result report also passed. The machine-readable record
is [`repository_validation.json`](../provenance/repository_validation.json).

## Offline release checks

```sh
python3.11 tools/check_release.py --root .
python3.11 tools/bundle_verification.py --check
.venv/bin/python -m pytest -q -m 'not integration and not docker and not live'
.venv/bin/ruff check secprbench tests examples tools
.venv/bin/python examples/contract_scanner.py \
  --input examples/public_input.json --output .work/example-findings.json \
  --run-id 012345abcdef
.venv/bin/secprbench report \
  --snapshot artifacts/results/results_265_opus55_high.json \
  --out .work/frozen-report
```

The data validator establishes the 265-pair/530-task cohort, paired hashes,
indexes, exclusions, supporting evidence links, and frozen-result accounting.
The verification checker establishes bundled asset integrity and PoC digest
consistency. Neither executes vulnerability reproducers.

The package tests cover schema and contract validation, history-free
materialization, host/private input separation, runner lifecycle, network-rule
construction, output validation, judging configuration and resume, and report
denominators. Portable-source tests use a local test repository; subprocess
harness tests use fixtures. No paid model provider is required for this suite.

Archive comparisons are opt-in with `SECPRBENCH_ARCHIVE_ROOT` and
`SECPRBENCH_LEGACY_DATA_ROOT`. They use external historical source data and are
not prerequisites for the offline suite. Docker and live-model tests are
separate and must not be inferred from mocked unit tests.

The CI workflow installs the package without the optional model-wrapper extra,
runs the release and verification checks, exercises the contract example, and
runs the frozen-result report, offline test suite, and lint. This is the
offline acceptance gate for a fresh checkout.

## Separate execution gates

1. **Docker infrastructure:** build pinned reviewer images and run
   `secprbench check --backend opus55 --harness direct_review`. Verify actual
   containment and API TLS reachability without a model call.
2. **Source/replay:** prepare pinned project revisions, check historical build
   prerequisites, and run selected exact PoCs. Publish per-case success,
   inconclusive outcomes, failures, and observed environment identities.
3. **Model evaluation:** run the assigned roster, validate each review/audit,
   judge it using the recorded configuration, and report complete denominators.

The release includes saved evidence and reports. It does not claim fresh Docker
containment, fresh historical replay, completed human judge auditing, or a newly
measured benchmark result.
