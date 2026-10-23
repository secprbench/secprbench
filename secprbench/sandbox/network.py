"""Install a fail-closed firewall in a waiting reviewer network namespace.

Only this short-lived helper receives NET_ADMIN. It shares the reviewer's
network namespace, has no task/credential mounts, and exits before the trusted
entrypoint releases the harness. The reviewer itself cannot alter these rules.
"""

from __future__ import annotations

import argparse
import ipaddress
import re
import subprocess


def _proxy_address(value: str) -> str:
    address = ipaddress.ip_address(value)
    if not isinstance(address, ipaddress.IPv4Address):
        raise ValueError("the egress proxy must have an IPv4 address")  # noqa: TRY004 - invalid address value
    if (
        address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_unspecified
        or address.is_reserved
    ):
        raise ValueError("the egress proxy must have a unicast bridge address")
    return str(address)


def network_rules(proxy_ip: str) -> dict[str, str]:
    """Return complete filter tables suitable for atomic iptables-restore.

    Docker rewrites its embedded resolver's destination port in the OUTPUT
    NAT hook. Match the original conntrack destination port to keep DNS
    blocked even though loopback is available to the local MCP tool server.
    """
    proxy = _proxy_address(proxy_ip)
    policies = ["*filter", ":INPUT DROP [0:0]", ":FORWARD DROP [0:0]", ":OUTPUT DROP [0:0]"]
    dns = [
        "-A OUTPUT -p udp -m conntrack --ctdir ORIGINAL --ctorigdstport 53 -j DROP",
        "-A OUTPUT -p tcp -m conntrack --ctdir ORIGINAL --ctorigdstport 53 -j DROP",
    ]
    ipv4 = [
        *policies,
        "-A INPUT -i lo -j ACCEPT",
        "-A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT",
        # The resolver's random listening port is visible in /proc/net/udp.
        # Block its address too, so direct access cannot bypass the port-53
        # conntrack check by using that post-DNAT port.
        "-A OUTPUT -d 127.0.0.11/32 -j DROP",
        *dns,
        "-A OUTPUT -o lo -j ACCEPT",
        "-A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT",
        f"-A OUTPUT -d {proxy}/32 -p tcp --dport 3128 -m conntrack --ctstate NEW -j ACCEPT",
        "COMMIT",
        "",
    ]
    ipv6 = [*policies, "-A INPUT -i lo -j ACCEPT", *dns, "-A OUTPUT -o lo -j ACCEPT", "COMMIT", ""]
    return {"ipv4": "\n".join(ipv4), "ipv6": "\n".join(ipv6)}


def helper_command(container_id: str, proxy_ip: str, image: str) -> list[str]:
    """Construct a mount-free, narrowly privileged helper invocation."""
    if not re.fullmatch(r"(?:[0-9a-f]{12,64}|r-[0-9a-f]{12})", container_id):
        raise ValueError("invalid reviewer container ID")
    proxy = _proxy_address(proxy_ip)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./:@-]*", image):
        raise ValueError("invalid helper image reference")
    return [
        "docker",
        "run",
        "--rm",
        "--network",
        f"container:{container_id}",
        "--cap-drop",
        "ALL",
        "--cap-add",
        "NET_ADMIN",
        "--user",
        "0",
        "--read-only",
        "--security-opt",
        "no-new-privileges:true",
        "--tmpfs",
        "/run:rw,nosuid,nodev,size=1m,mode=755",
        "--pids-limit",
        "64",
        "--memory",
        "128m",
        "--cpus",
        "1",
        "--entrypoint",
        "python",
        image,
        "-I",
        "-m",
        "secprbench.sandbox.network",
        "--apply",
        proxy,
    ]


def configure_network(container_id: str, proxy_ip: str, image: str) -> None:
    """Return only after the target namespace has a complete firewall.

    The host runner must keep the entrypoint gate closed if this raises.
    """
    try:
        subprocess.run(
            helper_command(container_id, proxy_ip, image),
            check=True,
            capture_output=True,
            text=True,
            timeout=45,
        )
    except subprocess.CalledProcessError as error:
        # This trusted helper receives no secrets, so its diagnostics are safe
        # to retain. They identify unsupported kernel/iptables configurations.
        detail = (error.stderr or "").strip()[-2000:]
        raise RuntimeError(f"network firewall helper failed (exit {error.returncode}): {detail}") from error


def apply_network_rules(proxy_ip: str) -> None:
    """Install both address-family policies, failing before the gate can open."""
    tables = network_rules(proxy_ip)
    # Set DROP before installing allow rules. Even partial failure leaves the
    # waiting namespace closed; the host must never release its entrypoint.
    for executable in ("iptables", "ip6tables"):
        for chain in ("OUTPUT", "INPUT", "FORWARD"):
            subprocess.run(
                [executable, "--wait", "5", "--policy", chain, "DROP"],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
    for family, executable in (("ipv4", "iptables-restore"), ("ipv6", "ip6tables-restore")):
        subprocess.run(
            [executable, "--wait", "5"],
            input=tables[family],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", required=True, metavar="PROXY_IP")
    args = parser.parse_args(argv)
    apply_network_rules(args.apply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
