import pytest
from pydantic import ValidationError

from secprbench.config import load_backend, BackendSpec, PROJECTS, load_project
from secprbench.harnesses.contract import load_harness
from secprbench.sandbox.proxy import write_compose, denied_events
from secprbench.sandbox.runner import docker_command


def test_all_backend_and_project_configs():
    for name in ("opus", "sonnet5", "fable", "claude", "glm", "grok", "minimax", "codex"):
        backend = load_backend(name)
        assert backend.model and backend.egress_hosts
    for name in PROJECTS:
        assert load_project(name)["verify"]["image"]


def test_backend_rejects_ip_and_unallowlisted_url():
    for hosts, url in [
        (["127.0.0.1"], ""),
        (["api.example.com"], "https://other.example.com"),
        (["api.example.com"], "http://api.example.com"),
    ]:
        with pytest.raises(ValidationError):
            BackendSpec(name="test", model="test", egress_hosts=hosts, base_url=url)


def test_container_minimal_mounts_and_no_secret_argv(tmp_path):
    backend = BackendSpec(
        name="test", model="test", egress_hosts=["api.example.com"], env={"SAMPLE_SECRET": "sensitive"}
    )
    command, env = docker_command(
        load_harness("direct_review"),
        backend,
        run_id="abcdef123456",
        project="curl",
        snapshot=tmp_path / "source",
        inputs=tmp_path / "input",
        outputs=tmp_path / "out",
        network="internal",
        proxy_ip="172.30.0.2",
    )
    joined = " ".join(command)
    assert "sensitive" not in joined and env["SAMPLE_SECRET"] == "sensitive"
    assert "--read-only" in command and "--cap-drop" in command and "--dns" in command
    assert command[command.index("--dns") + 1] == "127.0.0.1"
    assert joined.count("type=bind,") == 3
    assert "docker.sock" not in joined


def test_proxy_config_exact_host_connect_and_private_denials(tmp_path):
    backend = load_backend("opus")
    path = write_compose(backend, tmp_path)
    assert "internal: true" in path.read_text()
    text = (tmp_path / "squid.conf").read_text()
    assert "http_access deny !CONNECT" in text
    assert "http_access deny private" in text
    assert ".api.anthropic.com" not in text
    assert text.index("http_access deny private") < text.index("http_access allow allowed")


def test_denials_scoped_to_task_ip_and_start(tmp_path):
    path = tmp_path / "log"
    path.write_text(
        "100.5 0 172.1.0.2 TCP_DENIED/403 10 CONNECT example.com:443 - HIER_NONE/- text/html\n"
        "101.5 0 172.1.0.3 TCP_DENIED/403 10 CONNECT other.com:443 - HIER_NONE/- text/html\n"
    )
    assert len(denied_events(path, since=100, client_ip="172.1.0.2")) == 1
    assert not denied_events(path, since=101, client_ip="172.1.0.2")
