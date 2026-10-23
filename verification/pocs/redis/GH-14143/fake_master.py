import socket, sys, time

PORT = int(sys.argv[1])
MARKER = (b'0123456789' * 4)  # 40-byte EOF marker, intentionally never sent again

def read_command(f):
    line = f.readline()
    if not line:
        return None
    if not line.startswith(b'*'):
        return line.strip().split()
    n = int(line[1:].strip())
    args = []
    for _ in range(n):
        l2 = f.readline()
        ln = int(l2[1:].strip())
        data = f.read(ln)
        f.read(2)
        args.append(data)
    return args

srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(('127.0.0.1', PORT))
srv.listen(1)
conn, addr = srv.accept()
f = conn.makefile('rb')

while True:
    cmd = read_command(f)
    if cmd is None:
        break
    name = cmd[0].upper()
    if name == b'PING':
        conn.sendall(b'+PONG\r\n')
    elif name == b'REPLCONF':
        conn.sendall(b'+OK\r\n')
    elif name == b'PSYNC':
        replid = b'a' * 40
        conn.sendall(b'+FULLRESYNC ' + replid + b' 0\r\n')
        conn.sendall(b'$EOF:' + MARKER + b'\r\n')
        # Crafted RDB stream: valid header + SELECTDB + a RDB_TYPE_HASH_METADATA (24)
        # key, then an intentionally truncated 8-byte minExpire field (only 3 bytes
        # sent), followed by closing the connection -- simulating a broken
        # replication link / short read exactly while reading the HFE min-expire
        # time field.
        payload = b'REDIS0012'
        payload += bytes([0xFE, 0x00])          # SELECTDB 0
        payload += bytes([0x18])                # object type = RDB_TYPE_HASH_METADATA (24)
        payload += bytes([0x01]) + b'x'         # key "x" (len=1)
        payload += bytes([0x11, 0x22, 0x33])    # 3 of 8 minExpire bytes, then EOF
        conn.sendall(payload)
        try:
            conn.shutdown(socket.SHUT_WR)
        except OSError:
            pass
        time.sleep(3)
        try:
            conn.close()
        except OSError:
            pass
        break
    else:
        conn.sendall(b'+OK\r\n')
srv.close()
