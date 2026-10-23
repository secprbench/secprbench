import socket, threading

HOST = "127.0.0.1"
PORT = 8110

def handle(conn):
    f = conn.makefile("rwb")
    f.write(b"+OK fake pop3 server ready\r\n")
    f.flush()
    while True:
        line = f.readline()
        if not line:
            break
        cmd = line.decode(errors="replace").strip()
        up = cmd.upper()
        if up.startswith("CAPA"):
            # Reject CAPA so curl falls back to clear-text auth immediately
            f.write(b"-ERR unknown command\r\n")
        elif up.startswith("USER"):
            f.write(b"+OK\r\n")
        elif up.startswith("PASS"):
            f.write(b"+OK Logged in\r\n")
        elif up.startswith("DELE"):
            # Single-line-only response, no multi-line body, no dot terminator
            f.write(b"+OK marked for deletion\r\n")
        elif up.startswith("RETR"):
            # Multi-line dot-terminated response with an actual body,
            # sent in one shot so the body bytes land in the same read
            # as the status line (pp->overflow path).
            f.write(b"+OK 12 octets\r\nHello World\r\n.\r\n")
        elif up.startswith("QUIT"):
            f.write(b"+OK bye\r\n")
            f.flush()
            break
        else:
            f.write(b"+OK\r\n")
        f.flush()
    try:
        conn.close()
    except Exception:
        pass

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen(5)
    while True:
        conn, _ = s.accept()
        t = threading.Thread(target=handle, args=(conn,), daemon=True)
        t.start()

if __name__ == "__main__":
    main()
