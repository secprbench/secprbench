# Evaluation walkthrough

Run commands from the repository root after the offline installation in the
[README](../README.md). The repository is ready for inspection and
configuration; model availability, credentials, Docker access, and upstream
revision availability are properties of your execution environment.

## 1. Inspect and validate the released data

```sh
python3.11 tools/check_release.py --root .
```

`data/roster.json` is the execution authority. `instances/*.jsonl` is a convenient
export for analysis; it contains private labels and must not be mounted in a
reviewer container. Frozen source evidence can retain historical absolute paths
as provenance. Use the roster and current manifests for portable file lookup.

## 2. Prepare source

`prepare` clones a project using the upstream URL in its project configuration.
It does not run a model. By default, clones live under
`~/.cache/secprbench/repos`, or `$XDG_CACHE_HOME/secprbench/repos`.

```sh
.venv/bin/secprbench prepare --project curl
```

Use `SECPRBENCH_REPOS_ROOT` to relocate all clones, or `SECPRBENCH_CURL_REPO`
to reuse an existing curl clone. Equivalent per-project variables are supported.
The runner needs a clone for every selected project and each task's pinned
commit. For a chosen task, `prepare --task` checks that commit and fetches it
if it is absent. It leaves an existing checkout's working tree unchanged.

This example selects the first curl buggy task from the roster and materializes
its public input and history-blocked snapshot:

```sh
.venv/bin/python - <<'PY'
import json
import subprocess
from pathlib import Path

roster = json.loads(Path('data/roster.json').read_text())
entry = next(row for row in roster['entries'] if row['project'] == 'curl')
task = str(Path('data') / entry['buggy']['path'])
subprocess.run(['.venv/bin/secprbench', 'prepare', '--project', 'curl',
                '--task', task], check=True)
subprocess.run(['.venv/bin/secprbench', 'materialize', '--project', 'curl',
                '--task', task, '--output', '.work/materialized-curl'], check=True)
PY
```

The output contains `workspace/` and `input/`; `input/` contains only
`input.json` and `brief.md`. The materializer exports `task.commit_sha`.
See [protocol](PROTOCOL.md) for companion-snapshot semantics and
[known issues](KNOWN_ISSUES.md) for patch-fidelity limits.

## 3. Configure and build the reviewer

Configure `configs/backends/*.yaml` with the model, exact HTTPS host allowlist,
and authentication method you intend to evaluate. Copy the configuration tree
outside the repository and set `SECPRBENCH_CONFIG_DIR` to use custom settings.
Do not add credential values to versioned files.

For native Anthropic API authentication, the backend supports `api_key_env`
or `api_key_file` with `api_key_target: ANTHROPIC_API_KEY`. For subscription
authentication, omit those fields and select a credential document with
`SECPRBENCH_CLAUDE_AUTH_FILE` if automatic selection is unsuitable.
Codex supports `SECPRBENCH_CODEX_AUTH_FILE`. Credential documents remain outside
the repository; the reviewer receives only the selected authentication material.

The following builds the supplied Docker images with a separately installed
Claude Code 2.1.283 executable. Adjust the binary location if necessary.

```sh
.venv/bin/secprbench build-images \
  --claude-binary "$HOME/.local/share/claude/versions/2.1.283"
.venv/bin/secprbench check --harness direct_review --backend opus55
```

Image builds download dependencies. The `check` command tests real containment
and configured API TLS reachability without asking a model to review code.
It requires a working Docker daemon and a nonroot reviewer identity. See
[containment](SANDBOX.md). The offline release validator (`tools/check_release.py`) is a separate,
Docker-free check.

Model-backed host compatibility tools may additionally require
`.venv/bin/pip install -e '.[agent]'`. The optional dependency is not required
for data checks or offline reports.

## 4. Review, judge, and report

This bounded run evaluates a subset of curl tasks. `--limit` limits task
assignments. Inspect `manifest.json` to confirm assigned pairs and failures.
Omit `--limit` for all selected tasks, and omit `--projects` for the full roster.

```sh
.venv/bin/secprbench run \
  --roster data/roster.json --data-root data \
  --harness direct_review --backend opus55 \
  --projects curl --limit 2 --concurrency 1 \
  --output .work/example-run
.venv/bin/secprbench judge --run-dir .work/example-run
.venv/bin/secprbench report --run-dir .work/example-run \
  --out .work/example-report
```

The reviewer and judge are separate model calls. The default current judge is
`claude-opus-5-5`, high reasoning effort, Claude Code 2.1.283, using
`criteria-first-v1` with no tools or web. `SECPRBENCH_CLAUDE` selects the host
judge executable; `SECPRBENCH_JUDGE_AUTH_FILE` can select its credential document.
Changing model, effort, prompt, CLI, or tools creates a different evaluation
configuration and must be reported. See [judging](JUDGE.md).

Runs preserve assignments, task/findings hashes, and completed or failed outputs.
Rerunning with an identical configuration resumes valid completed work. Keep
infrastructure and review failures in the denominator; an error is not an empty
successful prediction. Heavy runtime files use `SECPRBENCH_WORK_ROOT`, defaulting
to `~/.cache/secprbench/work`; use a suitable disk for large projects.

## 5. Integrate a different scanner

Start with the [contract example](../examples/README.md), then create a harness:

```sh
.venv/bin/secprbench harness scaffold my_scanner --output .work/harnesses
```

Implement the generated `run.py`, build its image, and use its YAML as the
`--harness` argument. The generated starter intentionally raises until a scanner
is implemented. Harnesses receive only `/workspace`, `/task/input.json`, and
`/task/brief.md` and write the public prediction envelope to `/out/findings.json`.
See the [full contract](HARNESS_CONTRACT.md).

For a comparison or artifact submission, retain the exact roster hash, package
revision, backend/harness configuration, image IDs, scanner version, prompt,
budgets, prediction files, run manifests, audit records, judge configuration and
verdicts, and resulting reports. Submit failures and incomplete assignments as
such. Record any protocol deviations. This repository does not yet expose a
hosted submission service or leaderboard.
