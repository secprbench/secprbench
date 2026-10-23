import socket
import sys
import time
import re

HOST = '127.0.0.1'
PORT = 7777


class Conn:
    def __init__(self):
        self.s = socket.create_connection((HOST, PORT), timeout=60)
        self.s.settimeout(60)
        self.f = self.s.makefile('rb')
        self.pending = 0

    def send(self, *args):
        buf = ("*%d\r\n" % len(args)).encode()
        for a in args:
            ab = a if isinstance(a, bytes) else str(a).encode()
            buf += ("$%d\r\n" % len(ab)).encode() + ab + b"\r\n"
        self.s.sendall(buf)
        self.pending += 1

    def read_reply(self):
        line = self.f.readline()
        if not line:
            raise ConnectionError("eof from server")
        t = line[0:1]
        rest = line[1:-2]
        if t in (b'+', b':', b'-'):
            return rest
        elif t == b'$':
            n = int(rest)
            if n == -1:
                return None
            data = self.f.read(n)
            self.f.read(2)
            return data
        elif t == b'*':
            n = int(rest)
            if n == -1:
                return None
            return [self.read_reply() for _ in range(n)]
        else:
            raise ValueError("unknown reply type: %r" % line)

    def drain(self):
        out = None
        while self.pending > 0:
            out = self.read_reply()
            self.pending -= 1
        return out

    def cmd(self, *args):
        self.send(*args)
        return self.drain()

    def info_field(self, field):
        reply = self.cmd("INFO", "all")
        text = reply.decode(errors='replace') if isinstance(reply, bytes) else str(reply)
        m = re.search(r'^%s:(.*)$' % re.escape(field), text, re.MULTILINE)
        return m.group(1).strip() if m else None


def main():
    c = Conn()
    print("PING ->", c.cmd("PING"))
    c.cmd("CONFIG", "SET", "hz", "100")
    c.cmd("CONFIG", "SET", "activedefrag", "no")
    c.cmd("CONFIG", "RESETSTAT")
    c.cmd("CONFIG", "SET", "active-defrag-threshold-lower", "7")
    c.cmd("CONFIG", "SET", "active-defrag-cycle-min", "65")
    c.cmd("CONFIG", "SET", "active-defrag-cycle-max", "75")
    c.cmd("CONFIG", "SET", "active-defrag-ignore-bytes", "1500kb")
    c.cmd("CONFIG", "SET", "maxmemory", "0")
    c.cmd("CONFIG", "SET", "hash-max-listpack-value", "512")
    c.cmd("CONFIG", "SET", "hash-max-listpack-entries", "10")

    dummy_field = "x" * 400
    fields = 16
    n = 3000

    BATCH = 2000
    print("populating hashes with HFE fields + ballast keys...")
    t0 = time.time()
    for i in range(n):
        for j in range(fields):
            c.send("HSET", "h%d" % i, dummy_field + str(j), "v")
            c.send("HEXPIRE", "h%d" % i, "9999999", "FIELDS", "1", dummy_field + str(j))
            c.send("SET", "k%d_%d" % (i, j), dummy_field)
            if c.pending >= BATCH:
                c.drain()
        c.send("EXPIRE", "h%d" % i, "9999999")
        if c.pending >= BATCH:
            c.drain()
    c.drain()
    print("populate done in %.1fs" % (time.time() - t0))

    print("deleting ballast keys to fragment memory...")
    t0 = time.time()
    for i in range(n):
        for j in range(fields):
            c.send("DEL", "k%d_%d" % (i, j))
            if c.pending >= BATCH:
                c.drain()
    c.drain()
    print("delete done in %.1fs" % (time.time() - t0))

    time.sleep(0.2)

    try:
        print("frag ratio:", c.info_field("allocator_frag_ratio"))
    except Exception as e:
        print("info failed (maybe crashed already):", e)
        sys.exit(1)

    print("enabling activedefrag...")
    try:
        c.cmd("CONFIG", "SET", "activedefrag", "yes")
    except Exception as e:
        print("config set activedefrag failed/crashed:", e)
        sys.exit(1)

    deadline = time.time() + 90
    started = False
    while time.time() < deadline:
        try:
            v = c.info_field("total_active_defrag_time")
        except Exception as e:
            print("connection broke while polling for defrag start (likely crashed):", e)
            sys.exit(1)
        if v and v != "0":
            started = True
            print("defrag started, total_active_defrag_time=", v)
            break
        time.sleep(0.2)

    if not started:
        print("defrag never started (maybe activedefrag unsupported in this build)")

    deadline = time.time() + 90
    while time.time() < deadline:
        try:
            running = c.info_field("active_defrag_running")
        except Exception as e:
            print("connection broke while waiting for defrag stop (likely crashed):", e)
            sys.exit(1)
        if running == "0":
            break
        time.sleep(0.2)

    try:
        print("final PING ->", c.cmd("PING"))
    except Exception as e:
        print("final ping failed (likely crashed):", e)
        sys.exit(1)

    print("DONE, server survived")
    sys.exit(0)


if __name__ == "__main__":
    main()
