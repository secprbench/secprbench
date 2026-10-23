# Criteria-first judgment

The judge asks whether a reported finding identifies the reference target's
causal failure and whether that failure is present in the evaluated snapshot.
It uses the private reference, submitted findings, and evaluated diff. Nearby
line overlap, similar CWE labels, and a different defect are not sufficient.

The current release configuration in `configs/judge.yaml` matches the latest
paper judge: Claude Opus 5.5 (`claude-opus-5-5`), high reasoning effort,
Claude Code 2.1.283, `criteria-first-v1`, a 30,000-character relevant-diff budget,
and no tools or web. Historical Sonnet 4.6 configuration is explicitly separated
under `configs/judges/`; it is not the current default.

```sh
secprbench judge --run-dir .work/example-run
```

The host requires an authenticated Claude executable.
`SECPRBENCH_CLAUDE` selects its path; `SECPRBENCH_JUDGE_AUTH_FILE` can select the
credential file. Calls use private temporary configuration homes, an empty
working directory, no persistent session, disabled skills/settings sources,
an empty strict MCP configuration, and an explicitly empty tool list.
No private reference enters the reviewer container.

CLI overrides such as `--model`, `--reasoning-effort`, `--claude-version`, and
`--config` must be recorded as a changed evaluation configuration. The optional
historical `--paper-tools` path is a separate host-side compatibility mode;
it does not reproduce the current no-tools paper judge.

Successful reviews are loaded from the run manifest. The judge verifies task
and findings hashes. Public `predictions` and the legacy nested `findings`
format can be normalized for evaluation. Empty successful findings produce a
deterministic negative without a model call. Malformed JSON, contradictory
verdicts, and identity mismatches trigger retry/failure, not an inferred hit.
Each judged task receives `verdict.json` and `judge_logs/`, and the run receives
`judge_summary.json`. Resume fingerprints include the relevant configuration.

## Interpretation

On a buggy task, a credited target detection contributes to target recall.
On a companion, a positive verdict means the judge considers the target still
present. A negative verdict does not say whether the scanner alleged a repaired
failure, reported a different issue, or reported nothing. Consequently,
**companion target-presence verdicts are not a standalone false-alarm metric**.
Report finding volume and target judgments separately until a dedicated
false-alarm adjudication protocol is completed.

The copied latest-paper results have not received a completed independent human
judge audit. Preserve that limitation. No model judgment was rerun while
filtering the frozen cohort for this repository.
