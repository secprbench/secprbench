"""Kernel-helper contract tests; real containment is exercised separately."""

import subprocess
from unittest.mock import Mock

import pytest

from secprbench.sandbox.entrypoint import wait_for_network_gate
from secprbench.sandbox.network import (
    apply_network_rules,
    configure_network,
    helper_command,
    network_rules,
)


def test_firewall_defaults_and_narrow_allow_rules():
    rules = network_rules("172.30.0.2")
    for table in rules.values():
        assert ":OUTPUT DROP [0:0]" in table
        assert ":INPUT DROP [0:0]" in table
        assert ":FORWARD DROP [0:0]" in table
        assert "--ctorigdstport 53 -j DROP" in table
        assert table.index("--ctorigdstport 53") < table.index("-A OUTPUT -o lo -j ACCEPT")
        assert table.endswith("COMMIT\n")
    assert "-d 172.30.0.2/32 -p tcp --dport 3128" in rules["ipv4"]
    assert "-A OUTPUT -d 127.0.0.11/32 -j DROP" in rules["ipv4"]
    assert rules["ipv4"].count("--ctstate NEW -j ACCEPT") == 1
    assert "--ctstate" not in rules["ipv6"]
    assert rules["ipv6"].count("-A OUTPUT") == 3  # two DNS denials, loopback allow


@pytest.mark.parametrize(
    "address",
    [
        "::1",
        "::",
        "::ffff:172.30.0.2",
        "0.0.0.0",
        "127.0.0.1",
        "169.254.169.254",
        "224.0.0.1",
        "255.255.255.255",
        "172.30.0.2/24",
        "proxy",
        "172.30.0.2\nCOMMIT",
    ],
)
def test_proxy_address_validation(address):
    with pytest.raises(ValueError):
        network_rules(address)


def test_helper_has_only_network_capability_and_no_mounts():
    command = helper_command("a" * 64, "172.30.0.2", "secprbench-harness:0.1.0")
    assert command[command.index("--network") + 1] == "container:" + "a" * 64
    assert command[command.index("--cap-drop") + 1] == "ALL"
    assert command[command.index("--cap-add") + 1] == "NET_ADMIN"
    assert command[command.index("--user") + 1] == "0"
    assert "--privileged" not in command
    assert not ({"--mount", "-v", "--volume", "-e", "--env", "--env-file"} & set(command))
    assert command[command.index("secprbench-harness:0.1.0") + 1] == "-I"
    assert command[-4:] == ["-m", "secprbench.sandbox.network", "--apply", "172.30.0.2"]


@pytest.mark.parametrize(
    "container,image",
    [
        ("--privileged", "image:1"),
        ("host", "image:1"),
        ("a" * 64, "--privileged"),
        ("a" * 64, "image\nother"),
    ],
)
def test_helper_rejects_unsafe_identifiers(container, image):
    with pytest.raises(ValueError):
        helper_command(container, "172.30.0.2", image)


def test_host_waits_for_checked_helper(monkeypatch):
    run = Mock()
    monkeypatch.setattr(subprocess, "run", run)
    configure_network("a" * 64, "172.30.0.2", "image:1")
    assert run.call_args.kwargs["check"] is True
    assert run.call_args.kwargs["timeout"] == 45
    run.side_effect = subprocess.CalledProcessError(1, "docker")
    with pytest.raises(RuntimeError, match="firewall helper failed"):
        configure_network("a" * 64, "172.30.0.2", "image:1")


def test_apply_drops_both_families_before_allow_rules(monkeypatch):
    run = Mock()
    monkeypatch.setattr(subprocess, "run", run)
    apply_network_rules("172.30.0.2")
    calls = run.call_args_list
    assert len(calls) == 8
    assert all(call.args[0][-1] == "DROP" for call in calls[:6])
    assert calls[6].args[0][0] == "iptables-restore"
    assert calls[7].args[0][0] == "ip6tables-restore"
    assert calls[6].kwargs["input"] == network_rules("172.30.0.2")["ipv4"]
    assert all(call.kwargs["check"] for call in calls)


def test_failed_policy_does_not_install_allow_rules(monkeypatch):
    run = Mock(side_effect=subprocess.CalledProcessError(1, "iptables"))
    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(subprocess.CalledProcessError):
        apply_network_rules("172.30.0.2")
    assert run.call_count == 1


def test_gate_rejects_missing_config(monkeypatch):
    monkeypatch.delenv("SECPRBENCH_NETWORK_GATE", raising=False)
    with pytest.raises(RuntimeError, match="must be"):
        wait_for_network_gate(0)


def test_gate_requires_regular_file_and_ready_content(tmp_path, monkeypatch):
    gate = tmp_path / "gate"
    monkeypatch.setenv("SECPRBENCH_NETWORK_GATE", "/out/.network-ready")
    monkeypatch.setattr("secprbench.sandbox.entrypoint.Path", lambda _: gate)
    with pytest.raises(TimeoutError):
        wait_for_network_gate(0)
    gate.write_text("in-progress")
    with pytest.raises(TimeoutError):
        wait_for_network_gate(0)
    gate.write_text("ready\n")
    wait_for_network_gate(0)
    gate.unlink()
    target = tmp_path / "target"
    target.write_text("ready")
    gate.symlink_to(target)
    with pytest.raises(RuntimeError, match="symlink"):
        wait_for_network_gate(0)
