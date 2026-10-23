"""Key files retain path-only configuration and select the provider's auth header."""

import json

import pytest
from pydantic import ValidationError

from secprbench.config import BackendSpec
from secprbench.harnesses.contract import HarnessSpec
from secprbench.sandbox.runner import _credential_file, docker_command


def backend(tmp_path, **kwargs):
    key_file = tmp_path / "test.key"
    key_file.write_text("dummy-test-credential\n")
    return BackendSpec(
        name="test", model="test", api_key_file=str(key_file), egress_hosts=["api.anthropic.com"], **kwargs
    )


def test_native_anthropic_key_target_uses_api_key_and_skips_oauth(tmp_path):
    spec = backend(tmp_path, api_key_target="ANTHROPIC_API_KEY")
    harness = HarnessSpec(name="direct_review", image="test", command=["true"])
    additions = spec.environment()
    assert additions["ANTHROPIC_API_KEY"] == "dummy-test-credential"
    assert "ANTHROPIC_AUTH_TOKEN" not in additions
    assert _credential_file(harness, spec) is None
    assert "dummy-test-credential" not in json.dumps(spec.model_dump())
    command, env = docker_command(
        harness,
        spec,
        run_id="abcdef123456",
        project="curl",
        snapshot=tmp_path / "source",
        inputs=tmp_path / "input",
        outputs=tmp_path / "out",
        network="internal",
        proxy_ip="172.20.0.2",
    )
    assert "ANTHROPIC_API_KEY" in command
    assert env["ANTHROPIC_API_KEY"] == "dummy-test-credential"
    assert "dummy-test-credential" not in " ".join(command)
    assert not any("/credentials/" in item for item in command)


@pytest.mark.parametrize("name,target", [("test", "ANTHROPIC_AUTH_TOKEN"), ("codex", "OPENAI_API_KEY")])
def test_unset_target_preserves_existing_backend_behavior(tmp_path, name, target):
    spec = backend(tmp_path).model_copy(update={"name": name})
    assert spec.environment()[target] == "dummy-test-credential"


def test_explicit_auth_target_applies_to_environment_key_source(monkeypatch):
    monkeypatch.setenv("SECPRBENCH_TEST_KEY", "dummy-test-credential")
    spec = BackendSpec(
        name="test",
        model="test",
        api_key_env="SECPRBENCH_TEST_KEY",
        api_key_target="ANTHROPIC_API_KEY",
        egress_hosts=["api.anthropic.com"],
    )
    assert spec.environment()["ANTHROPIC_API_KEY"] == "dummy-test-credential"
    assert "SECPRBENCH_TEST_KEY" not in spec.environment()


@pytest.mark.parametrize("invalid", ["HOME", "PATH", "ANTHROPIC_API_KEY=x", ""])
def test_auth_target_rejects_arbitrary_environment_variables(tmp_path, invalid):
    with pytest.raises(ValidationError):
        backend(tmp_path, api_key_target=invalid)
