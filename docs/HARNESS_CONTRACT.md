# Harness contract

A harness runs inside the reviewer sandbox. It receives a source tree at
`/workspace` and public task files at `/task/input.json` and `/task/brief.md`.
`SECPRBENCH_RUN_ID` is the opaque 12-character hexadecimal task identifier.
The private task archive, ground truth, and verification records stay on the host.

The harness writes `/out/findings.json` using the
[public prediction schema](../secprbench/harnesses/prediction.schema.json):

```json
{
  "instance_id": "012345abcdef",
  "model": "scanner-model-and-version",
  "predictions": [
    {
      "title": "Example security failure",
      "message": "Explain the causal failure and why the input can reach it.",
      "file": "src/main.c",
      "start_line": 12,
      "severity": "high",
      "bug_type": "UseAfterFree",
      "confidence": 0.9
    }
  ]
}
```

An empty array denotes a completed review with no findings. Missing, malformed,
failed, timed-out, or budget-exhausted output is a failed review. The host validates
the schema and assigned identifier, normalizes locations and bug types, and
drops findings outside the changed-file set with an explicit count. Paths must
remain inside the source tree; line numbers refer to the reviewed snapshot.

Optional trajectories, raw findings, usage, and coverage records belong beneath
`/out`. Do not add private IDs, labels, commit hashes from private metadata,
or references to prompts, filenames, or trajectories. The host writes the private
mapping after the container exits.

## Configure an implementation

`configs/harnesses/<name>.yaml` defines the image, command array, and budgets.
Command elements are individual arguments without shell expansion. Substitutions
include `{workspace}`, `{input}`, `{output}`, `{model}`, `{project}`, `{run_id}`,
and `{max_turns}`. The only supported output path is `/out/findings.json`.
The host enforces `timeout_seconds`; supported CLIs can additionally use
`max_turns`. Codex has no corresponding turn-limit flag and must use a timeout.

`writable_workspace: true` requests an ephemeral source copy; it does not expose
the host checkout or Git history. Most scanners should use a read-only source
mount. Authentication is injected at runtime, never included in image layers.

```sh
secprbench harness scaffold my_scanner --output .work/harnesses
```

The command creates a Dockerfile, YAML, and Python starter. Implement the scanner
and convert its output into the public envelope before using it in evaluation.
The starter deliberately raises until implemented. An executable format-only
example is in [`examples/`](../examples/README.md).

## Included implementations

- `direct_review` uses the pinned Claude CLI through `coding-agent-wrapper` and
  the archived recall-oriented review prompts. It exposes finding and coverage
  reporting tools. Optional project context changes the prompt configuration.
- `defending` wraps the vendored security-review skill and converts its output.
  The static skill retains the adjacent Apache-2.0 license. Do not infer that
  this static harness reproduces every later external paper campaign adapter.
- `codex` invokes a pinned Codex CLI with structured output and ignores host
  project settings. Its own internal sandbox is disabled inside the enforced
  Docker boundary. It disables unnecessary plugin, app, web, and telemetry
  startup traffic in its command configuration.

Pin the image and CLI for comparisons, and retain their identities in the run
manifest. The runner resolves image tags before assigning work. Offline contract
and subprocess tests verify interface behavior; real [containment](SANDBOX.md)
and model runs require separate execution.
