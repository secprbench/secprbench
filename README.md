# SecPRBench

SecPRBench evaluates whether a code reviewer finds the security flaw in a real
change. Each case is the upstream change that introduced a vulnerability in one
of nine C, C++, and Rust projects. The reviewer receives the diff, the commit
message, and a source snapshot without usable Git history, but no vulnerability
description, and must identify the flaw and explain its root cause. A companion
task shows the repaired change at the upstream fixing revision.

This repository contains the benchmark data and the evaluation harness:
**265 cases / 530 paired review tasks**, private reference evidence for the
evaluator, the Docker review sandbox, the criteria-first judge, and the frozen
results reported in the paper. The construction pipeline that collected and
verified the cases is not part of this repository. Results and saved review
trajectories are browsable at the
[results website](https://yijan4845.github.io/secprbench-results/).

| Project | Cases | Tasks |
|---|---:|---:|
| curl | 26 | 52 |
| FFmpeg | 61 | 122 |
| Firefox | 27 | 54 |
| FreeType | 15 | 30 |
| OpenSSL | 29 | 58 |
| Redis | 16 | 32 |
| SQLite | 33 | 66 |
| V8 | 44 | 88 |
| Wasmtime | 14 | 28 |
| **Total** | **265** | **530** |

Older introductions remain eligible; there is no introduction-date cutoff.
Read the [data card](docs/DATA_CARD.md) and [known issues](docs/KNOWN_ISSUES.md)
before interpreting results.

## Start with offline checks

Python 3.10 or newer is required; the examples use Python 3.11. Installing
dependencies uses the network. The checks themselves need neither Docker,
credentials, nor model calls.

```sh
python3.11 tools/check_release.py --root .
python3.11 tools/bundle_verification.py --check
python3.11 -m venv .venv
.venv/bin/pip install -e '.[test]'
.venv/bin/python -m pytest -q -m 'not integration and not docker and not live'
.venv/bin/secprbench --help
```

The release validator checks the roster, exact task and evidence hashes, index
consistency, excluded identities, paired counts, and the frozen results. Known
retained issues are reported separately from integrity failures. A passing
offline check does not mean every vulnerability has been rebuilt and replayed.

## Evaluate a scanner

The [contract example](examples/README.md) runs without a model or Docker and
demonstrates the public prediction format. To implement a real scanner:

```sh
.venv/bin/secprbench harness scaffold my_scanner --output .work/harnesses
```

For source preparation, isolated Docker review, judging, and reporting, follow
the [evaluation walkthrough](docs/USAGE.md). The runner uses
`data/roster.json --data-root data`. Model-backed evaluation requires your own
provider credentials and uses the chosen provider's resources.

## Data and results

- [`data/roster.json`](data/roster.json): canonical paired execution roster, with
  task paths relative to `data/` and hashes of the original task bytes.
- [`instances/`](instances/): one JSONL per project plus a global index for
  convenient case and task access. These files contain private labels and must
  not be mounted into a reviewer container.
- [`provenance/`](provenance/): source hashes, eligibility policy, nine exclusion
  decisions, and issues retained for follow-up.
- [`artifacts/results/`](artifacts/results/): the 265-case frozen paper results
  for eight direct reviewer configurations, with derived counts.
- [`verification/`](verification/): bundled proof-of-concept inputs, replay
  records, and a coverage manifest. See [verification](docs/VERIFICATION.md).

The criteria-first judge credits the specified causal failure only when it is
present in the evaluated snapshot. **Zero positive companion verdicts do not
establish zero false alarms.** Historical companions use the upstream fixing
snapshot for review, while verification can use a composed repaired tree.
Those identities are preserved and must not be conflated. See
[scoring](docs/JUDGE.md) and [protocol](docs/PROTOCOL.md).

## Documentation

- [Data card and selection](docs/DATA_CARD.md)
- [Evaluation and custom scanners](docs/USAGE.md)
- [Evaluation protocol](docs/PROTOCOL.md)
- [Public and private schemas](docs/SCHEMA.md)
- [Harness contract](docs/HARNESS_CONTRACT.md)
- [Sandbox and containment](docs/SANDBOX.md)
- [Verification coverage](docs/VERIFICATION.md)
- [Scoring and frozen results](docs/REPORT.md)
- [Known issues](docs/KNOWN_ISSUES.md)
- [Validation](docs/VALIDATION.md)
- [Release notes](docs/PUBLICATION.md)
- [License scope](LICENSE_SCOPE.md), [attribution notices](NOTICE), and
  [citation information](docs/CITATION.md)
