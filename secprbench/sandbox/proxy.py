"""Generate an isolated network and an auditable CONNECT-only Squid proxy."""

from __future__ import annotations

import fcntl
import os
import subprocess
from pathlib import Path

import yaml

from secprbench.config import BackendSpec
from secprbench.io import atomic_write


def squid_config(hosts: list[str]) -> str:
    # Hosts have already been validated by BackendSpec. No leading dots: exact hosts only.
    if not hosts or any(not __import__("re").fullmatch(r"[A-Za-z0-9.-]+", host) for host in hosts):
        raise ValueError("invalid proxy allowlist")
    return "\n".join(
        [
            "http_port 3128",
            "visible_hostname secprbench-egress",
            "pid_filename /tmp/squid.pid",
            "acl CONNECT method CONNECT",
            "acl TLS_ports port 443",
            "acl private dst 0.0.0.0/8 10.0.0.0/8 100.64.0.0/10 127.0.0.0/8 169.254.0.0/16 172.16.0.0/12 192.168.0.0/16 224.0.0.0/4 ::1/128 fc00::/7 fe80::/10",
            r"acl ip_literal url_regex -i ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+: ^\[",
            "acl allowed dstdomain " + " ".join(hosts),
            "http_access deny !CONNECT",
            "http_access deny !TLS_ports",
            "http_access deny ip_literal",
            "http_access deny !allowed",
            "http_access deny private",
            "http_access allow allowed",
            "http_access deny all",
            "cache deny all",
            "cache_store_log none",
            "access_log stdio:/var/log/squid/access.log",
            "cache_log /dev/stderr",
            "logfile_rotate 0",
            "shutdown_lifetime 1 seconds",
            "",
        ]
    )


def write_compose(backend: BackendSpec, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    logs = directory / "logs"
    logs.mkdir(exist_ok=True)
    # Squid runs as its unprivileged image user, and writes only this dedicated directory.
    logs.chmod(0o755)
    atomic_write(directory / "squid.conf", squid_config(backend.egress_hosts))
    config = {
        "services": {
            "egress": {
                "image": "secprbench-egress:1",
                "user": f"{os.getuid()}:{os.getgid()}",
                "networks": ["agents", "egress"],
                "volumes": [
                    f"{directory.resolve() / 'squid.conf'}:/etc/squid/squid.conf:ro",
                    f"{logs.resolve()}:/var/log/squid:rw",
                ],
                "read_only": True,
                "tmpfs": ["/tmp", "/run"],
                "cap_drop": ["ALL"],
                "security_opt": ["no-new-privileges:true"],
                "pids_limit": 128,
                "mem_limit": "256m",
            }
        },
        "networks": {
            "agents": {"internal": True, "name": f"secprbench-{backend.name}-agents"},
            "egress": {"name": f"secprbench-{backend.name}-egress"},
        },
    }
    path = directory / "compose.yaml"
    atomic_write(path, yaml.safe_dump(config, sort_keys=False))
    return path


def start_proxy(backend: BackendSpec, directory: Path) -> tuple[str, str]:
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / ".lock").open("w") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        return _start_proxy(backend, directory)


def _start_proxy(backend: BackendSpec, directory: Path) -> tuple[str, str]:
    path = write_compose(backend, directory)
    prefix = ["docker", "compose", "-p", f"secprbench-{backend.name}", "-f", str(path)]
    subprocess.run([*prefix, "up", "-d"], check=True, capture_output=True, text=True, timeout=120)
    container = subprocess.run(
        [*prefix, "ps", "-q", "egress"], check=True, capture_output=True, text=True, timeout=30
    ).stdout.strip()
    network = f"secprbench-{backend.name}-agents"
    import json

    inspected = json.loads(
        subprocess.run(
            ["docker", "inspect", container], check=True, capture_output=True, text=True, timeout=30
        ).stdout
    )[0]
    address = inspected["NetworkSettings"]["Networks"][network]["IPAddress"]
    return network, address


def denied_events(
    log: Path, *, since: float = 0, client_ip: str | None = None, until: float | None = None
) -> list[dict]:
    events = []
    if not log.exists():
        return events
    for line in log.read_text(errors="replace").splitlines():
        parts = line.split()
        if len(parts) < 7 or "DENIED" not in parts[3]:
            continue
        try:
            timestamp = float(parts[0])
        except ValueError:
            continue
        if (
            timestamp >= since
            and (until is None or timestamp <= until)
            and (client_ip is None or parts[2] == client_ip)
        ):
            events.append(
                {"event": "denied_egress", "timestamp": timestamp, "client": parts[2], "target": parts[6]}
            )
    return events
