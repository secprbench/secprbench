"""Identical loopback MQTT and debug allocation-fault input for three curl trees."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

PORT = 43091
CONNACK = bytes.fromhex("20020000")


def main() -> int:
    received: list[str] = []
    server_errors: list[str] = []
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", PORT))
    listener.listen(1)
    listener.settimeout(4)

    def server() -> None:
        try:
            with listener:
                conn, _ = listener.accept()
                with conn:
                    conn.settimeout(0.3)
                    received.append(conn.recv(4096).hex())
                    conn.sendall(CONNACK)
                    deadline = time.monotonic() + 3.5
                    while time.monotonic() < deadline:
                        try:
                            chunk = conn.recv(4096)
                        except TimeoutError:
                            continue
                        if not chunk:
                            break
                        received.append(chunk.hex())
        except (OSError, TimeoutError) as error:
            server_errors.append(str(error))

    thread = threading.Thread(target=server, daemon=True)
    thread.start()
    with tempfile.TemporaryDirectory(prefix="secprbench-gh16823-") as temporary:
        memlog = Path(temporary) / "memory.log"
        env = {
            **os.environ,
            "CURL_SMALLSENDS": "1",
            "CURL_ENTROPY": "SECP",
            "CURL_MEMDEBUG": str(memlog),
        }
        command = [
            "/work/src/curl",
            "--disable",
            "--noproxy",
            "*",
            "--max-time",
            "3",
            "--verbose",
            "--output",
            "/dev/null",
            f"mqtt://127.0.0.1:{PORT}/topic",
        ]
        try:
            proc = subprocess.run(command, env=env, capture_output=True, timeout=8, check=False)
        except subprocess.TimeoutExpired as error:
            print(f"POC_TIMEOUT: {error}", flush=True)
            return 2
        thread.join(timeout=5)
        memory_lines = memlog.read_text(errors="replace").splitlines() if memlog.exists() else []
        relevant = [
            line for line in memory_lines if " send(1) = 1" in line or line.startswith("LIMIT ")
        ]
        limit_indices = [
            i
            for i, line in enumerate(memory_lines)
            if line.startswith("LIMIT ") and line.endswith("strdup.c:91 malloc reached memlimit")
        ]
        targeted_limit = bool(
            limit_indices
            and any(" send(1) = 1" in line for line in memory_lines[: limit_indices[0]])
        )
        print(f"POC_CURL_EXIT={proc.returncode}")
        print(f"POC_SERVER_RECEIVED={','.join(received)}")
        print(f"POC_SERVER_ERRORS={','.join(server_errors)}")
        print(f"POC_TARGETED_LIMIT={int(targeted_limit)}")
        for line in relevant[-8:]:
            print(f"POC_MEMORY={line}")
        # MQTT wire bytes can appear in curl's verbose output. DockerRunner
        # decodes container output as UTF-8, so replace only invalid display
        # bytes while keeping the raw host preflight evidence unchanged.
        if proc.stdout:
            sys.stdout.write(proc.stdout.decode("utf-8", errors="replace"))
        if proc.stderr:
            sys.stderr.write(proc.stderr.decode("utf-8", errors="replace"))
        # Runner retains only the tail of a long ASan trace. Repeat the
        # decisive self-check after curl's output so the frozen result records
        # which allocation was blocked for the crashing version as well.
        print(f"POC_FINAL_CURL_EXIT={proc.returncode}", file=sys.stderr)
        print(f"POC_FINAL_SERVER_RECEIVED={','.join(received)}", file=sys.stderr)
        print(f"POC_FINAL_TARGETED_LIMIT={int(targeted_limit)}", file=sys.stderr)
        sys.stdout.flush()
        sys.stderr.flush()
        if not targeted_limit:
            return 2
        if proc.returncode == 27:
            return 0
        if proc.returncode != 0:
            return 1
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
