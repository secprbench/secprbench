<div align="center">
  <img src="docs/assets/logo.svg" alt="SecPRBench logo" width="84">
  <h1>SecPRBench</h1>
  <p><b>Can Agentic Code Review Catch Vulnerabilities Before They Are Merged?</b></p>
  <p>
    <a href="https://arxiv.org/abs/2610.33509"><img src="https://img.shields.io/badge/Paper-arXiv-b31b1b?style=for-the-badge" alt="Paper"></a>
    <a href="https://secprbench.github.io/#/results"><img src="https://img.shields.io/badge/Leaderboard-Live-0f9fa8?style=for-the-badge" alt="Leaderboard"></a>
    <a href="https://secprbench.github.io/#/tasks"><img src="https://img.shields.io/badge/Case_explorer-5%2C290_trajectories-f97316?style=for-the-badge" alt="Case explorer"></a>
  </p>
  <p>
    <a href="CHANGELOG.md"><img src="https://img.shields.io/badge/release-v0.2.0-2f81f7" alt="Release v0.2.0"></a>
    <img src="https://img.shields.io/badge/python-3.10%2B-3776ab?logo=python&logoColor=white" alt="Python 3.10+">
    <a href="docs/SANDBOX.md"><img src="https://img.shields.io/badge/review-Docker_sandbox-2496ed?logo=docker&logoColor=white" alt="Docker review sandbox"></a>
  </p>
</div>
<br>

SecPRBench asks whether an AI code reviewer can catch a vulnerability on the
day it was committed. Each case is the real upstream change that introduced a
vulnerability in one of nine widely deployed C, C++, and Rust projects, from
FFmpeg and OpenSSL to V8 and Firefox. The reviewer receives the diff, the
commit message, and a source snapshot. It gets no advisory, no usable Git
history, and no hint, and it must identify the flaw and explain its root cause.
A paired companion task shows the repaired change at the upstream fixing
revision.

Most security-review benchmarks derive the reviewed change from its later fix.
SecPRBench instead traces each vulnerability back to the commit that introduced
it and validates the case, mostly by proof-of-concept replay. This repository
contains the benchmark data, the Docker review sandbox, the criteria-first
judge, and the frozen results reported in the paper.

## News

- **[2026-10]** 🌐 The [results website](https://secprbench.github.io/) is live,
  with the full leaderboard, a case explorer with annotated ground-truth lines,
  and 5,290 saved review trajectories.
- **[2026-10]** 📄 The paper is on
  [arXiv](https://arxiv.org/abs/2610.33509). Across eight frontier models,
  recall ranges from 32.5% to 78.1%, and four models are statistically tied at
  the top.
- **[2026-10]** 🚀 SecPRBench v0.2.0 is public: 265 cases / 530 paired tasks,
  the evaluation harness, and the frozen paper results
  ([changelog](CHANGELOG.md)).

## The task

| The reviewer gets | The reviewer never sees |
|---|---|
| The diff of the change under review | The vulnerability report, advisory, or CVE text |
| The commit message and any upstream PR text | The later fix |
| A source snapshot at that revision, with Git history blocked | The reference root cause and proof of concept |
| Its own tools, inside a Docker sandbox that can reach only the model API | The bug ID, private labels, or which task is its pair |

A criteria-first LLM judge (Claude Opus 5.5, high effort, no tools or web)
credits a finding only when it explains the reference root cause and that
failure is present in the reviewed snapshot. Recall is the share of all 265
introducing changes where the judge credits the reviewer; failed and missing
runs stay in the denominator. In a 50-record audit by the authors, the judge
agreed on 46 records (92%). See [scoring](docs/JUDGE.md).

## Leaderboard

Direct review on the 265 introducing changes. The three GPT models run in the
Codex CLI at `xhigh` reasoning effort, and the other models run in Claude Code.
The top four are statistically tied.

| # | Model | Agent CLI | Found | Recall |
|:-:|---|---|--:|--:|
| 1 | Grok 4.6 | Claude Code | 207 | **78.1%** |
| 2 | GPT-6 sol (xhigh) | Codex CLI | 202 | 76.2% |
| 3 | GLM 5.3 | Claude Code | 198 | 74.7% |
| 4 | Claude Opus 5.5 (high) | Claude Code | 196 | 74.0% |
| 5 | Claude Sonnet 5 | Claude Code | 157 | 59.2% |
| 6 | GPT-5.6 sol (xhigh) | Codex CLI | 148 | 55.8% |
| 7 | GPT-6 luna (xhigh) | Codex CLI | 147 | 55.5% |
| 8 | MiniMax M3 | Claude Code | 86 | 32.5% |
| | *Any of the eight* | | *242* | *91.3%* |

Security-focused harnesses change the picture in opposite directions:

| Configuration | Found | Recall | Compared with direct review by the same model |
|---|--:|--:|---|
| Claude Opus 5.5 in Anthropic's Defending Code harness | 212 | 80.0% | +7.7 points on the 260 tasks it completed, at a higher cost |
| GPT-5.6 sol in OpenAI's Codex Security | 126 | 47.5% | −8.3 points, mostly by abstaining |

## Quick start

### 1. Run the offline checks

Python 3.10 or newer is required; the examples use Python 3.11. Installing
dependencies uses the network. The checks themselves need no Docker,
credentials, or model calls.

```sh
python3.11 tools/check_release.py --root .
python3.11 tools/bundle_verification.py --check
python3.11 -m venv .venv
.venv/bin/pip install -e '.[test]'
.venv/bin/python -m pytest -q -m 'not integration and not docker and not live'
.venv/bin/secprbench --help
```

The release validator checks the roster, task and evidence hashes, indexes,
paired counts, and the frozen results.

### 2. Review a few tasks with a model

This needs Docker and your own provider credentials, configured in
`configs/backends/` as described in the [evaluation walkthrough](docs/USAGE.md).
Bundled backends include Claude Opus 5.5 and Sonnet 5, GPT-5.6 sol through
Codex, Grok 4.6, GLM 5.3, and MiniMax M3.

```sh
# Clone the upstream source (no model calls)
.venv/bin/secprbench prepare --project curl

# Build the review images and test the sandbox
.venv/bin/secprbench build-images \
  --claude-binary "$HOME/.local/share/claude/versions/2.1.283"
.venv/bin/secprbench check --harness direct_review --backend opus55

# Review two curl tasks, judge the findings, and write a report
.venv/bin/secprbench run \
  --roster data/roster.json --data-root data \
  --harness direct_review --backend opus55 \
  --projects curl --limit 2 --concurrency 1 \
  --output .work/example-run
.venv/bin/secprbench judge --run-dir .work/example-run
.venv/bin/secprbench report --run-dir .work/example-run --out .work/example-report
```

Omit `--projects` and `--limit` to run the full roster.

### 3. Evaluate your own scanner

The [contract example](examples/README.md) runs without a model or Docker and
shows the public prediction format. To start a real harness:

```sh
.venv/bin/secprbench harness scaffold my_scanner --output .work/harnesses
```

A harness receives only `/workspace`, `/task/input.json`, and `/task/brief.md`,
and writes its findings to `/out/findings.json`. See the
[harness contract](docs/HARNESS_CONTRACT.md).

## Repository layout

```text
data/                 Canonical roster (roster.json) and original task files
instances/            Per-project JSONL indexes; contain private labels, never mount in a reviewer container
secprbench/           The harness: materializer, sandbox runner, judge, and reports
configs/              Backend, harness, judge, and per-project configurations
artifacts/results/    Frozen results with derived counts
verification/         Bundled PoC inputs, replay records, and a coverage manifest
provenance/           Source hashes and selection records used by the validator
examples/             Offline scanner contract example
tools/                Release validator and verification bundler
docs/                 Data card, usage guide, harness contract, sandbox, schemas, and scoring
```

## License

This repository does not yet grant a blanket license for the SecPRBench code,
dataset, annotations, or PoC bundle. Upstream diffs, reports, and PoCs keep
their original licenses. See [license scope](LICENSE_SCOPE.md) and
[attribution notices](NOTICE).
