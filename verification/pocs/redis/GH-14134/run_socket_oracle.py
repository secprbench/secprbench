"""Reproduce Redis GH-14134 with one identical RESP command per revision.

This probe runs each supplied binary on an isolated Unix socket. It disables
Redis's optional crash-report walk so a production serverPanic reaches its
normal abort signal promptly. It does not edit the supplied source or binary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path

PANIC = "Guru Meditation: Redis built-in command declared keys positions not matching the arity requirements."
NORMAL = b"-ERR wrong number of arguments for 'get' command\r\n"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probe(label: str, binary: Path, request: bytes, output: Path) -> dict:
    sockdir = Path(tempfile.mkdtemp(prefix=f"sprb14134-{label}-", dir="/tmp"))
    sock = sockdir / "redis.sock"
    cmd = [str(binary), "--port", "0", "--unixsocket", str(sock),
           "--unixsocketperm", "700", "--save", "", "--appendonly", "no",
           "--io-threads", "2", "--loglevel", "warning", "--daemonize", "no",
           "--crash-log-enabled", "no", "--crash-memcheck-enabled", "no"]
    log = output / f"{label}_server.log"
    env = {**os.environ,
           "ASAN_OPTIONS": "abort_on_error=1:detect_leaks=0:allocator_may_return_null=1",
           "UBSAN_OPTIONS": "print_stacktrace=1:halt_on_error=1"}
    result = {"label": label, "binary": str(binary), "binary_sha256": digest(binary),
              "request_sha256": hashlib.sha256(request).hexdigest(), "command": cmd,
              "environment": {name: env[name] for name in ("ASAN_OPTIONS", "UBSAN_OPTIONS")}}
    try:
        with log.open("wb") as stream:
            process = subprocess.Popen(cmd, cwd=output, env=env, stdout=stream,
                                       stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 10
                while not sock.exists() and process.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.05)
                result["socket_ready"] = sock.exists()
                if sock.exists():
                    with socket.socket(socket.AF_UNIX) as client:
                        client.settimeout(3)
                        client.connect(str(sock))
                        client.sendall(request)
                        try:
                            result["reply_hex"] = client.recv(4096).hex()
                        except (TimeoutError, ConnectionError) as error:
                            result["reply_error"] = repr(error)
                    deadline = time.monotonic() + 3
                    while process.poll() is None and time.monotonic() < deadline:
                        time.sleep(0.05)
                result["exit_after_request"] = process.poll()
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                result["final_exit"] = process.returncode
        log_text = log.read_text(errors="replace")
        result["server_log"] = {"path": str(log), "sha256": digest(log)}
        result["has_redis_panic"] = PANIC in log_text
        reply = bytes.fromhex(result.get("reply_hex", ""))
        if result["has_redis_panic"] and process.returncode == -6:
            result["outcome"] = "production_serverPanic_SIGABRT"
        elif reply == NORMAL and not result["has_redis_panic"] and process.returncode == 0:
            result["outcome"] = "normal_arity_error"
        else:
            result["outcome"] = "anomaly"
        return result
    finally:
        shutil.rmtree(sockdir)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--binary", action="append", nargs=2, metavar=("LABEL", "PATH"),
                        required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.mkdir(parents=True)
    request = args.request.read_bytes()
    assert request == b"*1\r\n$3\r\nGET\r\n"
    results = [probe(label, Path(path).resolve(), request, args.output)
               for label, path in args.binary]
    manifest = {"schema_version": 1, "request": {"path": str(args.request),
                "sha256": digest(args.request)}, "results": results}
    (args.output / "results.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(args.output), "outcomes": {
        row["label"]: row["outcome"] for row in results}}, indent=2))


if __name__ == "__main__":
    main()
