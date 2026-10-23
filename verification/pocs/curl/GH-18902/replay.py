"""Replay curl/GH-18902 from a read-only /poc fixture against /work.

Exit 0 means OCSP rejection was enforced. Exit 1 means the 2023 regression
accepted a second connection despite a signed revoked response. Any setup
oracles failing exit 2, so an infrastructure problem cannot look protected.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path


POC = Path("/poc")
WORK = Path("/work")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(*args: str, timeout: int = 15) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, timeout=timeout)


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def check_fixture() -> str:
    fixture = json.loads((POC / "fixture-manifest.json").read_text())
    for name, expected in fixture["public_input_sha256"].items():
        if sha(POC / name) != expected:
            raise ValueError(f"fixture changed: {name}")
    if sha(POC / "server.key") != fixture["synthetic_private_key_sha256_not_mirrored"]["server.key"]:
        raise ValueError("synthetic server key changed")
    for label in ("good", "revoked"):
        checked = run("openssl", "ocsp", "-respin", str(POC / f"{label}.der"),
                      "-issuer", str(POC / "ca.crt"), "-cert", str(POC / "server.crt"),
                      "-CAfile", str(POC / "ca.crt"), "-no_nonce")
        if checked.returncode != 0 or "Response verify OK" not in checked.stdout + checked.stderr:
            raise ValueError(f"signed {label} OCSP response expired or invalid: {checked.stdout} {checked.stderr}")
        if f": {label}" not in checked.stdout + checked.stderr:
            raise ValueError(f"unexpected {label} OCSP status: {checked.stdout} {checked.stderr}")
    return sha(POC / "fixture-manifest.json")


def main() -> int:
    fixture_sha = check_fixture()
    static_lib = WORK / "lib/.libs/libcurl.a"
    if not static_lib.is_file():
        raise FileNotFoundError(static_lib)
    flags = run("bash", str(WORK / "curl-config"), "--static-libs")
    if flags.returncode:
        raise RuntimeError(f"curl-config failed: {flags.stderr}")
    link = [word for word in shlex.split(flags.stdout)
            if not word.endswith("/libcurl.a") and word != "-lcurl"]
    with tempfile.TemporaryDirectory(prefix="secprbench-gh18902-") as name:
        out = Path(name)
        client = out / "client"
        compiled = run("cc", "-Wall", "-Wextra", "-O0", "-g",
                       "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                       "-DCURL_STATICLIB", f"-I{WORK / 'include'}", str(POC / "client.c"),
                       "-o", str(client), str(static_lib), *link, timeout=45)
        if compiled.returncode:
            raise RuntimeError(f"client compile failed: {compiled.stdout} {compiled.stderr}")
        (out / "status.der").write_bytes((POC / "good.der").read_bytes())
        (out / "revoked-working.der").write_bytes((POC / "revoked.der").read_bytes())
        port = free_port()
        command = ["openssl", "s_server", "-tls1_2", "-cert", str(POC / "server.crt"),
                   "-cert_chain", str(POC / "ca.crt"), "-key", str(POC / "server.key"),
                   "-accept", f"127.0.0.1:{port}", "-status_file", str(out / "status.der"),
                   "-status_verbose", "-www", "-naccept", "2"]
        with (out / "server.log").open("w") as log:
            server = subprocess.Popen(command, cwd=out, stdout=log, stderr=subprocess.STDOUT)
            try:
                time.sleep(0.5)
                if server.poll() is not None:
                    raise RuntimeError("local OCSP server exited before client")
                env = {**os.environ,
                       "ASAN_OPTIONS": "abort_on_error=1:detect_leaks=0:allocator_may_return_null=1",
                       "UBSAN_OPTIONS": "print_stacktrace=1:halt_on_error=1"}
                observed = subprocess.run(
                    [str(client), str(port), str(POC / "ca.crt"),
                     str(out / "revoked-working.der"), str(out / "status.der")],
                    cwd=out, env=env, text=True, capture_output=True, timeout=35)
            finally:
                if server.poll() is None:
                    server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)
        log_text = (out / "server.log").read_text()
        first = re.search(r"(?m)^FIRST_RESULT=(\d+) ", observed.stderr)
        second = re.search(r"(?m)^SECOND_RESULT=(\d+) ", observed.stderr)
        print("ORACLE_FIXTURE_SHA256=" + fixture_sha)
        print("ORACLE_INPUT_GOOD_SHA256=" + sha(POC / "good.der"))
        print("ORACLE_INPUT_REVOKED_SHA256=" + sha(POC / "revoked.der"))
        print("ORACLE_CLIENT_EXIT=" + str(observed.returncode))
        print("ORACLE_FIRST_RESULT=" + (first.group(1) if first else "missing"))
        print("ORACLE_SECOND_RESULT=" + (second.group(1) if second else "missing"))
        print("ORACLE_SERVER_GOOD=" + str("Cert Status: good" in log_text).lower())
        print("ORACLE_SERVER_REVOKED=" + str("Cert Status: revoked" in log_text).lower())
        print("ORACLE_SESSION_OFFER=" + str("SSL reusing session" in observed.stderr or
                                            "SSL re-using session" in observed.stderr).lower())
        print("ORACLE_CLIENT_LOG_BEGIN")
        print(observed.stderr[-12000:])
        print("ORACLE_CLIENT_LOG_END")
        if (observed.returncode != 0 or not first or int(first.group(1)) != 0
                or "SSL certificate status: good" not in observed.stderr
                or not second or int(second.group(1)) not in {0, 91}
                or sha(out / "status.der") != sha(POC / "revoked.der")
                or "AddressSanitizer" in observed.stderr or "runtime error:" in observed.stderr):
            raise ValueError("local signed-status or client precondition failed")
        if int(second.group(1)) == 0:
            print("ORACLE_RESULT=VULNERABLE_OCSP_VALIDATION_BYPASS")
            return 1
        print("ORACLE_RESULT=PROTECTED_REVOKED_OCSP_REJECTED")
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"ORACLE_RESULT=INFRASTRUCTURE_OR_INVALID_INPUT: {error}", file=sys.stderr)
        sys.exit(2)
