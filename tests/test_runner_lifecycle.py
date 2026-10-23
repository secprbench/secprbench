"""Cancellation and cleanup regressions with no Docker or model service needed."""

import json
import subprocess
from concurrent.futures import CancelledError
from threading import Event
from types import SimpleNamespace

import pytest

from secprbench.config import BackendSpec
from secprbench.harnesses.contract import HarnessSpec
from secprbench.io import read_json, sha256_file, write_json
from secprbench.sandbox import network, runner


class DockerStub:
    def __init__(self, monkeypatch):
        self.commands = []
        self.container_id = "a" * 64
        self.returncode = None
        self.args = ["docker", "start", "-a", self.container_id]
        self.waits = []
        self.on_wait = None
        self.create_error = None
        self.cleanup_error = None
        monkeypatch.setattr(runner.subprocess, "run", self.run)
        monkeypatch.setattr(runner.subprocess, "Popen", lambda *args, **kwargs: self)
        monkeypatch.setattr(network, "configure_network", lambda *args: None)

    def run(self, command, **kwargs):
        self.commands.append(command)
        if command[:3] == ["docker", "image", "inspect"]:
            stdout = json.dumps([{"Id": "sha256:pinned", "Config": {"Entrypoint": ["python", "-I"]}}])
        elif command[:2] == ["docker", "create"]:
            if self.create_error:
                raise self.create_error
            stdout = self.container_id
        elif command[:2] == ["docker", "inspect"]:
            stdout = json.dumps(
                [
                    {
                        "NetworkSettings": {"Networks": {"internal": {"IPAddress": "172.20.0.3"}}},
                        "State": {"OOMKilled": False},
                    }
                ]
            )
        elif command[:3] == ["docker", "rm", "-f"]:
            self.returncode = 137
            if self.cleanup_error:
                raise self.cleanup_error
            stdout = ""
        else:
            raise AssertionError(command)
        return SimpleNamespace(stdout=stdout, stderr="", returncode=0)

    def poll(self):
        return self.returncode

    def wait(self, *, timeout):
        self.waits.append(timeout)
        if self.returncode is None and self.on_wait:
            self.on_wait(timeout)
        if self.returncode is None:
            self.returncode = 0
        return self.returncode

    def kill(self):
        self.returncode = -9


@pytest.fixture
def container_call(tmp_path, monkeypatch):
    docker = DockerStub(monkeypatch)
    args = (
        ["docker", "create", "--name", "r-abcdef123456", "mutable:latest", "-m", "example"],
        {
            "SECPRBENCH_HARNESS_IMAGE": "mutable:latest",
            "SECPRBENCH_HELPER_IMAGE": "sha256:helper",
            "HTTPS_PROXY": "http://172.20.0.2:3128",
        },
        tmp_path,
        60,
    )
    return docker, args


def test_execution_pins_image_and_preserves_entrypoint_then_reaps(container_call, monkeypatch):
    docker, args = container_call
    gate = args[2] / ".network-ready"
    gate.write_text("ready\n")
    helpers = []

    def configure(*values):
        assert not gate.exists(), "stale gate was not removed before container startup"
        helpers.append(values)

    monkeypatch.setattr(network, "configure_network", configure)
    result = runner.execute_container(*args)
    created = next(command for command in docker.commands if command[:2] == ["docker", "create"])
    assert "mutable:latest" not in created
    assert "sha256:pinned" in created
    assert created[-4:] == ["python", "-I", "-m", "example"]
    assert result["image_id"] == "sha256:pinned"
    assert helpers == [(docker.container_id, "172.20.0.2", "sha256:helper")]
    assert gate.read_text() == "ready\n"
    assert docker.commands[-1] == ["docker", "rm", "-f", docker.container_id]
    assert docker.waits[-1] == 5


def test_precancelled_execution_never_calls_docker(container_call):
    docker, args = container_call
    cancelled = Event()
    cancelled.set()
    with pytest.raises(CancelledError):
        runner.execute_container(*args, cancel_event=cancelled)
    assert not docker.commands


def test_cancel_during_firewall_setup_keeps_gate_closed_and_removes_container(container_call, monkeypatch):
    docker, args = container_call
    cancelled = Event()
    monkeypatch.setattr(network, "configure_network", lambda *args: cancelled.set())
    with pytest.raises(CancelledError):
        runner.execute_container(*args, cancel_event=cancelled)
    assert not (args[2] / ".network-ready").exists()
    assert docker.commands[-1] == ["docker", "rm", "-f", docker.container_id]


def test_active_cancellation_polls_then_removes_container(container_call):
    docker, args = container_call
    cancelled = Event()

    def interrupt(timeout):
        assert timeout <= 0.5
        cancelled.set()
        raise subprocess.TimeoutExpired(docker.args, timeout)

    docker.on_wait = interrupt
    with pytest.raises(CancelledError):
        runner.execute_container(*args, cancel_event=cancelled)
    assert docker.waits == [0.5, 5]
    assert docker.commands[-1] == ["docker", "rm", "-f", docker.container_id]


@pytest.mark.parametrize("error", [KeyboardInterrupt(), subprocess.TimeoutExpired("docker create", 60)])
def test_interrupted_create_cleans_unique_attempt_name(container_call, error):
    docker, args = container_call
    docker.create_error = error
    with pytest.raises(type(error)):
        runner.execute_container(*args)
    created = next(command for command in docker.commands if command[:2] == ["docker", "create"])
    name = created[created.index("--name") + 1]
    assert name.startswith("r-abcdef123456-") and len(name) == len("r-abcdef123456-") + 12
    assert docker.commands[-1] == ["docker", "rm", "-f", name]
    assert not docker.waits


def test_timeout_is_recorded_and_container_removed(container_call):
    docker, args = container_call
    result = runner.execute_container(*args[:3], timeout=0)
    assert result["exit_code"] == 124 and result["timed_out"]
    assert docker.commands[-1] == ["docker", "rm", "-f", docker.container_id]


def test_cleanup_error_preserves_primary_failure_and_reaps_client(container_call, monkeypatch, caplog):
    docker, args = container_call
    docker.cleanup_error = subprocess.TimeoutExpired("docker rm", 30)

    def fail(*args):
        raise RuntimeError("firewall setup failed")

    monkeypatch.setattr(network, "configure_network", fail)
    with pytest.raises(RuntimeError, match="firewall setup failed"):
        runner.execute_container(*args)
    assert "Container cleanup failed" in caplog.text
    assert docker.waits == [5]


def test_cleanup_failure_turns_success_into_failure(container_call):
    docker, args = container_call
    docker.cleanup_error = subprocess.TimeoutExpired("docker rm", 30)
    with pytest.raises(subprocess.TimeoutExpired):
        runner.execute_container(*args)


def roster_setup(tmp_path, monkeypatch, count=1):
    tasks = []
    for index in range(count):
        path = tmp_path / f"task{index}.json"
        write_json(
            path,
            {
                "task_id": f"task{index}",
                "bug_id": f"private{index}",
                "commit_sha": "a" * 40,
                "task_type": "buggy",
                "files": [{"path": "x.c", "status": "modified"}],
                "full_diff": "diff",
            },
        )
        tasks.append(path)
    roster = tmp_path / "roster.json"
    write_json(
        roster,
        {
            "entries": [
                {"project": "curl", "bug_id": f"private{index}", "buggy": {"path": str(path)}}
                for index, path in enumerate(tasks)
            ]
        },
    )
    monkeypatch.setattr(
        runner,
        "load_backend",
        lambda name: BackendSpec(name="test", model="test", egress_hosts=["api.example.com"]),
    )
    monkeypatch.setattr(
        runner, "load_harness", lambda name: HarnessSpec(name="test", image="review:latest", command=["true"])
    )
    monkeypatch.setattr(runner, "start_proxy", lambda *args: ("internal", "172.20.0.2"))
    images = {"review:latest": "sha256:review", "secprbench-harness:0.1.0": "sha256:helper"}
    monkeypatch.setattr(runner.subprocess, "run", lambda cmd, **kw: SimpleNamespace(stdout=images[cmd[-1]]))
    options = dict(
        roster=roster,
        data_root=tmp_path,
        backend_name="test",
        harness_name="test",
        run_dir=tmp_path / "run",
        work_root=tmp_path / "work",
        concurrency=1,
        task_type="buggy",
    )
    return options, tasks, images


def task_record(kwargs, status="cancelled"):
    task = read_json(kwargs["task_path"])
    return {
        "task_id": task["task_id"],
        "bug_id": task["bug_id"],
        "project": kwargs["project"],
        "task_type": "buggy",
        "task_sha256": sha256_file(kwargs["task_path"]),
        "status": status,
    }


def test_keyboard_interrupt_cancels_queue_signals_active_worker_and_preserves_record(tmp_path, monkeypatch):
    options, _, _ = roster_setup(tmp_path, monkeypatch, count=5)
    started = Event()
    active_calls = []

    def run_task(**kwargs):
        runner._check_cancelled(kwargs["cancel_event"])
        active_calls.append(kwargs["task_path"])
        started.set()
        assert kwargs["cancel_event"].wait(5), "active worker was not signalled before executor shutdown"
        return task_record(kwargs)

    def interrupted(futures):
        assert started.wait(5)
        raise KeyboardInterrupt()
        yield  # Match as_completed's lazy iterator behavior.

    monkeypatch.setattr(runner, "run_task", run_task)
    monkeypatch.setattr(runner, "as_completed", interrupted)
    with pytest.raises(KeyboardInterrupt):
        runner.run_roster(**options)
    assert len(active_calls) == 1
    records = read_json(options["run_dir"] / "manifest.json")["tasks"]
    assert len(records) == 1 and records[0]["status"] == "cancelled"


def test_cancellation_after_materialization_removes_snapshot_without_starting_docker(tmp_path, monkeypatch):
    options, tasks, _ = roster_setup(tmp_path, monkeypatch)
    cancelled = Event()

    def materialize(repo, sha, path):
        path.mkdir()
        cancelled.set()

    monkeypatch.setattr(runner, "materialize_snapshot", materialize)
    monkeypatch.setattr(runner, "load_project", lambda name: {"clone_dir": "unused"})
    monkeypatch.setattr(
        runner, "docker_command", lambda *args, **kwargs: pytest.fail("started after cancellation")
    )
    record = runner.run_task(
        task_path=tasks[0],
        project="curl",
        run_dir=options["run_dir"],
        secret=b"a" * 32,
        backend=runner.load_backend("test"),
        harness=runner.load_harness("test"),
        network="internal",
        proxy_ip="172.20.0.2",
        proxy_log=tmp_path / "proxy.log",
        cancel_event=cancelled,
    )
    assert record["status"] == "cancelled"
    root = options["run_dir"] / record["opaque_id"]
    assert not (root / "workspace").exists()
    assert read_json(root / "record.json")["status"] == "cancelled"


@pytest.mark.parametrize("changed_image", ["review:latest", "secprbench-harness:0.1.0"])
def test_entire_run_uses_pinned_harness_and_helper_ids_and_resume_binds_both(
    tmp_path, monkeypatch, changed_image
):
    options, _, images = roster_setup(tmp_path, monkeypatch, count=3)
    launched = []

    def run_task(**kwargs):
        launched.append((kwargs["harness"].image, kwargs["helper_image"]))
        images[changed_image] = "sha256:replacement"
        return task_record(kwargs, status="failed")

    monkeypatch.setattr(runner, "run_task", run_task)
    manifest = runner.run_roster(**options)
    assert launched == [("sha256:review", "sha256:helper")] * 3
    assert manifest["harness_image_id"] == "sha256:review"
    assert manifest["helper_image_id"] == "sha256:helper"
    with pytest.raises(ValueError, match="configuration changed"):
        runner.run_roster(**options)


@pytest.mark.parametrize("legacy_missing_target", [True, False])
def test_resume_normalizes_legacy_auth_target_but_rejects_explicit_change(
    tmp_path, monkeypatch, legacy_missing_target
):
    options, _, _ = roster_setup(tmp_path, monkeypatch)
    monkeypatch.setattr(runner, "run_task", lambda **kwargs: task_record(kwargs, status="failed"))
    manifest = runner.run_roster(**options)
    assert manifest["backend_spec"]["api_key_target"] is None
    if legacy_missing_target:
        manifest["backend_spec"].pop("api_key_target")
        write_json(options["run_dir"] / "manifest.json", manifest)
    resumed = runner.run_roster(**options)
    assert resumed["backend_spec"]["api_key_target"] is None
    explicit = runner.load_backend("test").model_copy(update={"api_key_target": "ANTHROPIC_API_KEY"})
    monkeypatch.setattr(runner, "load_backend", lambda name: explicit)
    with pytest.raises(ValueError, match="configuration changed"):
        runner.run_roster(**options)
