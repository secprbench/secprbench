"""Run the same remote Set-Cookie race against a built historical libcurl.

Without arguments this is the Docker verifier entrypoint: /poc is read-only,
/work is the built revision, and the harness is compiled against /work's static
libcurl. The optional host arguments are only for isolated package smoke tests.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_input(poc: Path) -> dict:
    frozen = json.loads((poc / "fixture-manifest.json").read_text())
    for filename, expected in frozen["input_sha256"].items():
        if sha(poc / filename) != expected:
            raise ValueError(f"PoC fixture hash changed: {filename}")
    config = json.loads((poc / "remote-cookie.poc").read_text())
    if config != {
        "initial_cookie": "race.test host-only foo=old",
        "replace_path": "/replace",
        "main_path": "/main",
        "response_header": "Set-Cookie: foo=new; Path=/",
        "pause_at_main_cookie_unlock": 3,
    }:
        raise ValueError("Unexpected remote cookie fixture")
    return config


def compile_harness(poc: Path, work: Path, output: Path) -> None:
    static_lib = work / "lib/.libs/libcurl.a"
    if not static_lib.is_file():
        raise FileNotFoundError(f"version-specific static libcurl missing: {static_lib}")
    flags = subprocess.run(["bash", str(work / "curl-config"), "--static-libs"],
                           text=True, capture_output=True, timeout=15, check=False)
    if flags.returncode:
        raise RuntimeError(f"version curl-config failed: {flags.stderr[-1000:]}")
    link = [arg for arg in shlex.split(flags.stdout)
            if arg != "-lcurl" and not arg.endswith("/libcurl.a")]
    command = ["g++", "-std=c++17", "-Wall", "-Wextra", "-O1", "-g",
               "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
               "-pthread", "-DCURL_STATICLIB", f"-I{work / 'include'}",
               str(poc / "cookie-race-remote.cpp"), "-o", str(output),
               str(static_lib), *link]
    compiled = subprocess.run(command, text=True, capture_output=True,
                              timeout=60, check=False)
    if compiled.returncode:
        raise RuntimeError(f"harness compile failed: {compiled.stdout[-1200:]} {compiled.stderr[-2200:]}")


class Server(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    requests: list[dict] = []
    response_header = "Set-Cookie: foo=new; Path=/"

    def do_GET(self) -> None:
        self.requests.append({"path": self.path, "cookie": self.headers.get("Cookie"),
                              "host": self.headers.get("Host")})
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.send_header("Connection", "close")
        if self.path == "/replace":
            name, value = self.response_header.split(": ", 1)
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format: str, *args: object) -> None:
        pass


def run_harness(executable: Path, config: dict) -> tuple[subprocess.CompletedProcess[bytes], list[dict]]:
    Server.requests = []
    Server.response_header = config["response_header"]
    server = ThreadingHTTPServer(("127.0.0.1", 0), Server)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    env = os.environ.copy()
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
                "http_proxy", "https_proxy", "all_proxy", "no_proxy"):
        env.pop(key, None)
    env["ASAN_OPTIONS"] = "detect_leaks=0:abort_on_error=1:halt_on_error=1"
    env["UBSAN_OPTIONS"] = "print_stacktrace=1:halt_on_error=1"
    try:
        process = subprocess.run(
            [str(executable), str(server.server_port),
             str(config["pause_at_main_cookie_unlock"])],
            env=env, capture_output=True, timeout=20, check=False,
        )
        requests = list(Server.requests)
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()
    return process, requests


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--poc-dir", type=Path, default=Path("/poc"))
    parser.add_argument("--work-dir", type=Path, default=Path("/work"))
    parser.add_argument("--host-executable", type=Path,
                        help="host-only smoke: use an already built exact revision")
    args = parser.parse_args(argv)
    config = verify_input(args.poc_dir)
    print("ORACLE_FIXTURE_SHA256=" + sha(args.poc_dir / "fixture-manifest.json"))
    print("ORACLE_REMOTE_INPUT_SHA256=" + sha(args.poc_dir / "remote-cookie.poc"))
    print("ORACLE_HARNESS_SHA256=" + sha(args.poc_dir / "cookie-race-remote.cpp"))
    with tempfile.TemporaryDirectory(prefix="secprbench-gh18457-") as temporary:
        binary = args.host_executable or Path(temporary) / "cookie-race"
        if args.host_executable is None:
            compile_harness(args.poc_dir, args.work_dir, binary)
        else:
            if not binary.is_file():
                raise FileNotFoundError(binary)
        process, requests = run_harness(binary, config)
    stderr = process.stderr.decode(errors="replace")
    print("ORACLE_CLIENT_EXIT=" + str(process.returncode))
    print("ORACLE_REQUEST_PATHS=" + ",".join(row["path"] for row in requests))
    print("ORACLE_REPLACEMENT_COMPLETED=" +
          str("REPLACE_COMPLETED_BEFORE_MAIN_CONTINUES" in stderr).lower())
    replacement_received = any(row["path"] == "/replace" and
                               row["cookie"] == "foo=old" for row in requests)
    if not replacement_received or "REPLACE_RESULT=0 HTTP=200" not in stderr:
        raise ValueError("Remote Set-Cookie replacement did not complete")
    if "REPLACE_COMPLETED_BEFORE_MAIN_CONTINUES" not in stderr:
        raise ValueError("Cookie race timing did not occur")
    if process.returncode != 0 and "heap-use-after-free" in stderr:
        print("ORACLE_RESULT=VULNERABLE_REMOTE_COOKIE_UAF")
        print("ORACLE_ASAN_LOG_BEGIN")
        print(stderr[-14000:])
        print("ORACLE_ASAN_LOG_END")
        return 1
    if (process.returncode == 0 and
            "MAIN_RESULT=0 HTTP=200 PAUSED=1" in stderr and
            any(row["path"] == "/main" for row in requests)):
        print("ORACLE_RESULT=PROTECTED_NO_UAF")
        return 0
    print("ORACLE_FAILURE_STDERR_SHA256=" + hashlib.sha256(process.stderr).hexdigest())
    raise ValueError("Unexpected process result, neither target UAF nor protected")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"ORACLE_RESULT=INFRASTRUCTURE_OR_INVALID_INPUT: {error}", file=sys.stderr)
        sys.exit(2)
