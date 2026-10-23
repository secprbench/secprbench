# Offline scanner contract example

This small example reads a synthetic public review input, validates it, emits
an empty prediction envelope, and validates the output through the real harness
contract. It performs no security analysis and is not a measured baseline.

After installing the package, run from the repository root:

```sh
.venv/bin/python examples/contract_scanner.py \
  --input examples/public_input.json \
  --output .work/example-findings.json \
  --run-id 012345abcdef
```

No model, Docker daemon, credential, source clone, or original workspace is
needed. Output explicitly identifies `contract-example-no-security-analysis`.
Inside a real runner container, use the assigned `SECPRBENCH_RUN_ID` rather than
the fixture identifier. Replace the empty predictions with findings produced by
your scanner and preserve errors as errors.

Generate a complete Docker harness starter with:

```sh
.venv/bin/secprbench harness scaffold my_scanner --output .work/harnesses
```

See the [harness contract](../docs/HARNESS_CONTRACT.md) and
[evaluation walkthrough](../docs/USAGE.md) for integration.
