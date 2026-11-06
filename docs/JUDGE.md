# Scoring

The judge decides whether a reported finding identifies the reference target's
causal failure and whether that failure is present in the reviewed snapshot. It
sees the private reference, the submitted findings, and the reviewed diff.
Nearby line overlap, a similar CWE label, or a different defect is not enough.

The default configuration in `configs/judge.yaml` matches the paper: Claude Opus
5.5 (`claude-opus-5-5`), high reasoning effort, Claude Code 2.1.283, the
`criteria-first-v1` prompt, a 30,000-character diff budget, and no tools or web
access.

```sh
secprbench judge --run-dir .work/example-run
```

The host needs an authenticated Claude executable. `SECPRBENCH_CLAUDE` selects
its path, and `SECPRBENCH_JUDGE_AUTH_FILE` selects the credential file. The
private reference never enters the reviewer container. Overrides such as
`--model`, `--reasoning-effort`, `--claude-version`, or `--config` create a
different evaluation configuration; report them with your results.

Empty findings produce a negative verdict without a model call. Malformed or
contradictory judge output is retried and otherwise recorded as a failure. Each
judged task receives `verdict.json` and `judge_logs/`, and the run receives
`judge_summary.json`.

## Metrics

Recall is the share of assigned buggy tasks where the judge credits a finding
with the target. Failed and missing reviews stay in the denominator. On a
companion task, a positive verdict means the judge considers the target still
present in the repaired code.
