"""Initialize ephemeral HOME as the reviewer, then exec the configured harness."""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path


def wait_for_network_gate(timeout_seconds: float = 30) -> None:
    """Wait before credentials or untrusted workspace content are accessed."""
    value = os.environ.get("SECPRBENCH_NETWORK_GATE", "")
    if value != "/out/.network-ready":
        raise RuntimeError("SECPRBENCH_NETWORK_GATE must be /out/.network-ready")
    gate = Path(value)
    deadline = time.monotonic() + timeout_seconds
    while True:
        if gate.is_symlink():
            raise RuntimeError("network readiness gate must not be a symlink")
        try:
            if gate.is_file() and gate.read_text().strip() == "ready":
                return
        except FileNotFoundError:
            pass  # The host may atomically replace the readiness marker.
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("network firewall was not ready within the startup deadline")
        time.sleep(min(0.1, remaining))


def claude_runtime_config(account_json: str = "") -> dict:
    """Retain only account identity needed for CLI OAuth refresh.

    Host settings, project history, hooks and arbitrary configuration never
    cross this boundary. Invalid identity types fail without echoing values.
    """
    config = {"hasCompletedOnboarding": True, "projects": {"/workspace": {"hasTrustDialogAccepted": True}}}
    if not account_json:
        return config
    try:
        account = json.loads(account_json)
    except json.JSONDecodeError as error:
        raise ValueError("Claude account metadata must be a JSON object") from error
    if not isinstance(account, dict):
        raise ValueError("Claude account metadata must be a JSON object")  # noqa: TRY004 - config value
    for key, expected_type in (("oauthAccount", dict), ("userID", str)):
        if key not in account:
            continue
        if not isinstance(account[key], expected_type):
            raise ValueError(f"invalid Claude account metadata type for {key}")
        config[key] = account[key]
    return config


def anthropic_runtime_profile(profile_json: str = "") -> dict:
    """Create the portable user-OAuth profile without host settings or paths."""
    try:
        source = json.loads(profile_json) if profile_json else {}
    except json.JSONDecodeError as error:
        raise ValueError("Anthropic profile metadata must be a JSON object") from error
    if not isinstance(source, dict):
        raise ValueError("Anthropic profile metadata must be a JSON object")  # noqa: TRY004 - config value
    profile = {"version": "1.0", "authentication": {"type": "user_oauth"}}
    for key in ("version", "organization_id", "workspace_id"):
        if key not in source:
            continue
        if not isinstance(source[key], str):
            raise ValueError(f"invalid Anthropic profile metadata type for {key}")
        profile[key] = source[key]
    auth = source.get("authentication", {})
    if not isinstance(auth, dict):
        raise ValueError("Anthropic authentication profile must be an object")  # noqa: TRY004 - config value
    if auth.get("type", "user_oauth") != "user_oauth":
        raise ValueError("Anthropic credential copies require a user_oauth profile")
    if "client_id" in auth:
        if not isinstance(auth["client_id"], str):
            raise ValueError("invalid Anthropic profile client_id")
        profile["authentication"]["client_id"] = auth["client_id"]
    return profile


def initialize_anthropic_auth(home: Path, source: Path, profile_json: str = "") -> Path | None:
    """Install a modern credential copy and its selected profile in tmpfs HOME."""
    if not source.is_file():
        return
    profile = anthropic_runtime_profile(profile_json)
    root = home / ".config/anthropic"
    for directory in (root, root / "credentials", root / "configs"):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    credential = root / "credentials/default.json"
    shutil.copyfile(source, credential)
    credential.chmod(0o600)
    config = root / "configs/default.json"
    config.write_text(json.dumps(profile))
    config.chmod(0o600)
    selector = root / "active_config"
    selector.write_text("default\n")
    selector.chmod(0o600)
    return root


def main() -> None:
    wait_for_network_gate()
    home = Path.home()
    for folder in (".claude", ".codex", ".cache", ".config"):
        (home / folder).mkdir(parents=True, exist_ok=True)
    # Credential mounts contain only one auth document, not host config or history.
    for source, destination in (
        ("/credentials/claude.json", home / ".claude/.credentials.json"),
        ("/credentials/codex.json", home / ".codex/auth.json"),
    ):
        if Path(source).is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            destination.chmod(0o600)
    anthropic_root = initialize_anthropic_auth(
        home,
        Path("/credentials/anthropic.json"),
        os.environ.pop("SECPRBENCH_ANTHROPIC_PROFILE", ""),
    )
    if anthropic_root is not None:
        os.environ["ANTHROPIC_CONFIG_DIR"] = str(anthropic_root)
    config = claude_runtime_config(os.environ.pop("SECPRBENCH_CLAUDE_ACCOUNT", ""))
    config_path = home / ".claude.json"
    config_path.write_text(json.dumps(config))
    config_path.chmod(0o600)
    if os.environ.get("SECPRBENCH_WRITABLE_WORKSPACE") == "1":
        shutil.copytree("/snapshot", "/workspace", dirs_exist_ok=True, symlinks=True)
    if len(sys.argv) < 2:
        raise SystemExit("expected a harness command")
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    main()
