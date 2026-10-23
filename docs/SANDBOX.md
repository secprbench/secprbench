# Reviewer containment

Each backend uses an internal Docker agent bridge and an outbound HTTPS CONNECT
proxy. The proxy permits only configured exact model/API hostnames on port 443.
It rejects other hosts, IP literals, private addresses, and link-local addresses.
Host-owned proxy logs support the per-container egress audit.

An internal bridge alone does not isolate host gateway or sibling-container
services. The runner therefore holds the reviewer behind a startup gate while
a short-lived trusted helper installs kernel network rules in its network
namespace. Only loopback, established responses, and the exact proxy address
are permitted; DNS and external IPv6 are blocked. The helper has no source or
credential mounts. Review starts only after the rules are installed successfully.

The reviewer uses a nonroot UID/GID, dropped capabilities, no-new-privileges,
a read-only root, and configured CPU, memory, PID, and timeout limits. Source
and public task input are mounted at `/workspace` and `/task`; output is writable
only at `/out`. Temporary home and scratch locations are isolated. An opt-in
writable-source harness receives a disposable snapshot, not the host checkout.

Only the selected credential document or provider environment values are
injected. Host settings, full home directories, sessions, and entire credential
directories are not mounted. Credentials are not persisted back to the host.
Reviewer-visible sources have no usable Git history. Private task/evidence
records and identity mappings remain outside the container mounts.

```sh
secprbench check --backend opus55 --harness direct_review
```

This real Docker check verifies the input/history/privacy boundary, nonroot
execution, external HTTPS/IP/DNS restrictions, host/sibling isolation,
API TLS reachability, and denied-request accounting. It makes no model call.
Run it for the actual backend/harness used in a study. Adding `--live-task` and
`--project` separately requests a model-backed review.

Image IDs are resolved before assignments. A changed image/configuration cannot
silently resume an earlier run. Interrupted workers retain assignments and
completed/failed records. Firewall setup errors, timeouts, OOM kills, denied
egress, invalid output, and audit failures remain failures rather than clean
negative predictions.

This repository's offline CI does not establish Docker availability or prove
fresh containment checks have run. Run the check on your own host before
reporting results.
