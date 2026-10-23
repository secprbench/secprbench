"""Copy one selected auth profile into disposable CLI configuration directories."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from ..io import write_json


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("Credential/profile document must contain a JSON object")  # noqa: TRY004
    return value


def _modern_source(env: dict[str, str]) -> Path:
    base = Path(env.get("ANTHROPIC_CONFIG_DIR", str(Path.home() / ".config/anthropic")))
    active_path = base / "active_config"
    active = active_path.read_text().strip() if active_path.is_file() else "default"
    if not re.fullmatch(r"[A-Za-z0-9_-]+", active):
        raise ValueError("Invalid active Anthropic profile name")
    return base / "credentials" / f"{active}.json"


def _modern_profile(source: Path) -> dict[str, Any]:
    """The CLI needs a profile as well as credentials, even for a valid token."""
    candidate = source.parent.parent / "configs" / source.name
    raw = _read_object(candidate) if candidate.is_file() else {}
    authentication = raw.get("authentication", {"type": "user_oauth"})
    if not isinstance(authentication, dict) or authentication.get("type") != "user_oauth":
        raise ValueError("Modern judge credentials require a user_oauth profile")
    result: dict[str, Any] = {"version": "1.0", "authentication": {"type": "user_oauth"}}
    if "client_id" in authentication:
        if not isinstance(authentication["client_id"], str):
            raise ValueError("OAuth client_id must be a string")  # noqa: TRY004
        result["authentication"]["client_id"] = authentication["client_id"]
    for key in ("organization_id", "workspace_id"):
        if key in raw:
            if not isinstance(raw[key], str):
                raise ValueError(f"Anthropic profile {key} must be a string")  # noqa: TRY004
            result[key] = raw[key]
    return result


def isolated_auth_environment(env: dict[str, str], directory: Path) -> dict[str, str]:
    """Set both CLI auth roots so there is no ambient host-profile fallback.

    `CLAUDE_CONFIG_DIR` alone does not isolate Claude 2.1.258: it still reads
    ~/.config/anthropic/credentials/default.json. Source files stay untouched;
    refreshes affect only the disposable copies.
    """
    result = dict(env)
    classic = directory / "claude-config"
    modern = directory / "anthropic-config"
    xdg = directory / "xdg-config"
    for folder in (classic, modern, xdg):
        folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    result.update(CLAUDE_CONFIG_DIR=str(classic), ANTHROPIC_CONFIG_DIR=str(modern), XDG_CONFIG_HOME=str(xdg))
    config: dict[str, Any] = {"hasCompletedOnboarding": True}
    external_auth = any(
        env.get(key) for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN")
    )
    if not external_auth:
        explicit = env.get("SECPRBENCH_JUDGE_AUTH_FILE")
        legacy_dir = Path(env.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude")))
        candidates = (
            [Path(explicit).expanduser()]
            if explicit
            else [
                _modern_source(env),
                legacy_dir / ".credentials.json",
                Path.home() / ".caw/auth/claude/credentials.json",
            ]
        )
        source = next((path for path in candidates if path.is_file()), None)
        if explicit and source is None:
            raise FileNotFoundError("Configured judge auth file does not exist")
        if source:
            credential = _read_object(source)
            if credential.get("type") == "oauth_token" and credential.get("access_token"):
                target = modern / "credentials/default.json"
                target.parent.mkdir(mode=0o700)
                (modern / "configs").mkdir(mode=0o700)
                write_json(modern / "configs/default.json", _modern_profile(source), mode=0o600)
                (modern / "active_config").write_text("default\n")
            else:
                target = classic / ".credentials.json"
                saved_path = (
                    Path.home() / ".claude.json"
                    if source.resolve() == (Path.home() / ".claude/.credentials.json").resolve()
                    else Path.home() / ".caw/auth/claude/config.json"
                )
                if saved_path.is_file():
                    saved = _read_object(saved_path)
                    config.update({key: saved[key] for key in ("oauthAccount", "userID") if key in saved})
            shutil.copyfile(source, target)
            target.chmod(0o600)
    write_json(classic / ".claude.json", config, mode=0o600)
    return result
