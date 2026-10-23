"""Deterministic localhost h2c response fixture for curl/GH-16955.

This is an adapted witness, not the reporter's original Caddy server.  It
records actual response bytes and HTTP/2 WINDOW_UPDATE frames received from
the client.  Install nothing system-wide: set PYTHONPATH to the extracted
python3-h2, python3-hpack, and python3-hyperframe packages.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import select
import socket
import ssl
import time
from pathlib import Path

from h2.config import H2Configuration
from h2.connection import H2Connection
from h2.events import ConnectionTerminated, RemoteSettingsChanged, RequestReceived, StreamReset, WindowUpdated
from h2.exceptions import StreamClosedError


CHUNK = bytes(range(256)) * 64
PORT = 18755


def content_hash(length: int) -> str:
    digest = hashlib.sha256()
    full, extra = divmod(length, len(CHUNK))
    for _ in range(full):
        digest.update(CHUNK)
    digest.update(CHUNK[:extra])
    return digest.hexdigest()


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ready", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--fast-mib", type=int, default=64)
    parser.add_argument("--slow-mib", type=int, default=64)
    parser.add_argument("--send-delay-ms", type=float, default=0.0)
    parser.add_argument("--tls-cert", type=Path)
    parser.add_argument("--tls-key", type=Path)
    args = parser.parse_args()
    fast_len = args.fast_mib * 1024 * 1024
    slow_len = args.slow_mib * 1024 * 1024

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", PORT))
    listener.listen(1)
    listener.settimeout(10)
    write_json(args.ready, {"port": PORT, "fast_sha256": content_hash(fast_len),
                            "slow_sha256": content_hash(slow_len)})

    accepted = time.monotonic()
    sock, _ = listener.accept()
    if args.tls_cert:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(args.tls_cert), str(args.tls_key))
        context.set_alpn_protocols(["h2"])
        sock = context.wrap_socket(sock, server_side=True)
        alpn = sock.selected_alpn_protocol()
    else:
        alpn = "h2c"
    sock.setblocking(False)
    conn = H2Connection(config=H2Configuration(client_side=False, header_encoding="utf-8"))
    conn.initiate_connection()
    outgoing = bytearray(conn.data_to_send())
    streams: dict[int, dict] = {}
    events: list[dict] = []
    incoming_bytes = 0
    outgoing_bytes = 0
    peer_closed = False
    until = time.monotonic() + args.timeout

    while time.monotonic() < until:
        readable, writable, _ = select.select([sock], [sock] if outgoing else [], [], 0.02)
        if readable or (args.tls_cert and sock.pending()):
            try:
                packet = sock.recv(262144)
            except (BlockingIOError, ssl.SSLWantReadError, ssl.SSLWantWriteError):
                packet = None
            if packet == b"":
                peer_closed = True
                break
            if packet:
                incoming_bytes += len(packet)
                for event in conn.receive_data(packet):
                    if isinstance(event, RequestReceived):
                        headers = dict(event.headers)
                        path = headers.get(":path", "")
                        length = slow_len if path == "/slow" else fast_len
                        streams[event.stream_id] = {
                            "path": path, "content_length": length,
                            "content_sha256": content_hash(length),
                            "bytes_sent": 0, "window_updates": 0,
                            "window_increment": 0, "finished": False,
                            "reset": False,
                        }
                        conn.send_headers(event.stream_id,
                                          [(":status", "200"), ("content-type", "application/octet-stream"),
                                           ("content-length", str(length))])
                        events.append({"event": "request", "stream": event.stream_id, "path": path})
                    elif isinstance(event, WindowUpdated):
                        if event.stream_id in streams:
                            streams[event.stream_id]["window_updates"] += 1
                            streams[event.stream_id]["window_increment"] += event.delta
                        events.append({"event": "window_update", "stream": event.stream_id,
                                       "delta": event.delta,
                                       "sent_at_update": streams.get(event.stream_id, {}).get("bytes_sent")})
                    elif isinstance(event, RemoteSettingsChanged):
                        events.append({"event": "remote_settings",
                                       "changed": {str(k): v.new_value for k, v in event.changed_settings.items()}})
                    elif isinstance(event, ConnectionTerminated):
                        events.append({"event": "connection_terminated", "error_code": event.error_code})
                    elif isinstance(event, StreamReset):
                        if event.stream_id in streams:
                            streams[event.stream_id]["reset"] = True
                        events.append({"event": "stream_reset", "stream": event.stream_id,
                                       "error_code": event.error_code})

        # Bound the queued output so the client receives HTTP/2 frames promptly.
        if len(outgoing) < 512 * 1024:
            for sid, stream in streams.items():
                if stream["reset"]:
                    continue
                for _ in range(16):
                    remaining = stream["content_length"] - stream["bytes_sent"]
                    if not remaining:
                        if not stream["finished"]:
                            conn.end_stream(sid)
                            stream["finished"] = True
                            events.append({"event": "body_complete", "stream": sid,
                                           "bytes_sent": stream["bytes_sent"]})
                        break
                    available = conn.local_flow_control_window(sid)
                    count = min(remaining, available, conn.max_outbound_frame_size, len(CHUNK))
                    if count <= 0:
                        break
                    try:
                        conn.send_data(sid, CHUNK[:count])
                    except StreamClosedError:
                        stream["reset"] = True
                        events.append({"event": "send_on_closed_stream", "stream": sid})
                        break
                    stream["bytes_sent"] += count
                outgoing.extend(conn.data_to_send())

        if writable and outgoing:
            try:
                n = sock.send(outgoing)
            except (BlockingIOError, ssl.SSLWantReadError, ssl.SSLWantWriteError):
                n = 0
            if n:
                del outgoing[:n]
                outgoing_bytes += n

        # Keep the TLS connection open until the client drains all DATA and
        # closes it.  An immediate close can strand a paused client's final
        # buffered bytes and create a false stall.
        if args.send_delay_ms:
            time.sleep(args.send_delay_ms / 1000)

    for sid, stream in streams.items():
        stream["remaining"] = stream["content_length"] - stream["bytes_sent"]
        try:
            stream["final_peer_window"] = conn.local_flow_control_window(sid)
        except StreamClosedError:
            stream["final_peer_window"] = None
    write_json(args.report, {
        "fixture": {"fast_length": fast_len, "slow_length": slow_len,
                    "fast_sha256": content_hash(fast_len), "slow_sha256": content_hash(slow_len),
                    "send_delay_ms": args.send_delay_ms},
        "streams": streams, "events": events, "incoming_bytes": incoming_bytes,
        "outgoing_bytes": outgoing_bytes, "peer_closed": peer_closed,
        "alpn": alpn,
        "duration_seconds": round(time.monotonic() - accepted, 3),
    })
    sock.close()
    listener.close()


if __name__ == "__main__":
    main()
