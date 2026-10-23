"""Only OAuth account identity may accompany the ephemeral credential copy."""

import json

import pytest

from secprbench.sandbox.entrypoint import claude_runtime_config


def test_account_identity_is_preserved_with_fresh_workspace_trust():
    account = {
        "oauthAccount": {"accountUuid": "synthetic-account", "organizationUuid": "synthetic-org"},
        "userID": "synthetic-user",
    }
    result = claude_runtime_config(json.dumps(account))
    assert result["oauthAccount"] == account["oauthAccount"]
    assert result["userID"] == account["userID"]
    assert result["hasCompletedOnboarding"] is True
    assert result["projects"] == {"/workspace": {"hasTrustDialogAccepted": True}}


def test_other_host_settings_are_discarded():
    host = {
        "oauthAccount": {},
        "userID": "test",
        "apiKey": "must-not-copy",
        "hooks": {"startup": "must-not-run"},
        "hasCompletedOnboarding": False,
        "projects": {"/host/private/path": {"history": ["must-not-copy"]}},
    }
    config = claude_runtime_config(json.dumps(host))
    assert set(config) == {"oauthAccount", "userID", "hasCompletedOnboarding", "projects"}
    assert config["hasCompletedOnboarding"] is True
    assert set(config["projects"]) == {"/workspace"}
    assert "must-not" not in json.dumps(config)


@pytest.mark.parametrize(
    "raw",
    [
        "invalid-json",
        "[]",
        "null",
        '"string"',
        '{"oauthAccount":"wrong-type"}',
        '{"userID":123}',
        '{"oauthAccount":null}',
    ],
)
def test_account_metadata_rejects_invalid_shapes(raw):
    with pytest.raises(ValueError):
        claude_runtime_config(raw)


def test_absent_identity_keeps_minimal_config():
    assert set(claude_runtime_config()) == {"hasCompletedOnboarding", "projects"}


def test_modern_profile_keeps_only_portable_oauth_fields():
    from secprbench.sandbox.entrypoint import anthropic_runtime_profile

    profile = {
        "version": "1.0",
        "organization_id": "synthetic-org",
        "workspace_id": "synthetic-workspace",
        "authentication": {"type": "user_oauth", "client_id": "synthetic-client", "token": "must-not-copy"},
        "created_by": "host-user",
        "hooks": {"startup": "must-not-run"},
        "path": "/host/private",
    }
    sanitized = anthropic_runtime_profile(json.dumps(profile))
    assert sanitized == {
        "version": "1.0",
        "organization_id": "synthetic-org",
        "workspace_id": "synthetic-workspace",
        "authentication": {"type": "user_oauth", "client_id": "synthetic-client"},
    }


@pytest.mark.parametrize(
    "raw",
    [
        "invalid-json",
        "[]",
        "null",
        '{"version":1}',
        '{"organization_id":[]}',
        '{"authentication":[]}',
        '{"authentication":{"type":"api_key"}}',
        '{"authentication":{"client_id":false}}',
    ],
)
def test_modern_profile_rejects_invalid_shapes(raw):
    from secprbench.sandbox.entrypoint import anthropic_runtime_profile

    with pytest.raises(ValueError):
        anthropic_runtime_profile(raw)


def test_modern_auth_writes_private_credentials_and_profile_selector(tmp_path):
    from secprbench.sandbox.entrypoint import initialize_anthropic_auth

    original = tmp_path / "mounted-credential.json"
    credential_bytes = b'{"access_token":"synthetic-only","refresh_token":"synthetic-only","expires_at":1}'
    original.write_bytes(credential_bytes)
    home = tmp_path / "ephemeral-home"
    initialize_anthropic_auth(home, original, '{"authentication":{"client_id":"synthetic-client"}}')
    root = home / ".config/anthropic"
    assert (root / "credentials/default.json").read_bytes() == credential_bytes
    assert original.read_bytes() == credential_bytes
    assert (root / "active_config").read_text() == "default\n"
    assert json.loads((root / "configs/default.json").read_text()) == {
        "version": "1.0",
        "authentication": {"type": "user_oauth", "client_id": "synthetic-client"},
    }
    for name in ("credentials/default.json", "configs/default.json", "active_config"):
        assert (root / name).stat().st_mode & 0o777 == 0o600


def test_modern_auth_absent_credentials_creates_nothing(tmp_path):
    from secprbench.sandbox.entrypoint import initialize_anthropic_auth

    home = tmp_path / "home"
    initialize_anthropic_auth(home, tmp_path / "missing", "not-evaluated-without-credentials")
    assert not home.exists()
