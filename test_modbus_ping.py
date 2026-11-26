#!/usr/bin/env python3
"""Self-check for modbus_ping.py against a fake Modbus server. Run: python3 test_modbus_ping.py"""
import socket
import struct
import threading

from modbus_ping import main, probe


def fake_server(reply):
    """Accepts connections; answers each FC04 request with reply(tid, unit, register)."""
    srv = socket.socket()
    srv.bind(('127.0.0.1', 0))
    srv.listen()

    def serve():
        while True:
            conn, _ = srv.accept()
            with conn:
                req = conn.recv(12)
                if len(req) == 12:
                    tid, _, _, unit, _, reg, _ = struct.unpack('>HHHBBHH', req)
                    conn.sendall(reply(tid, unit, reg))

    threading.Thread(target=serve, daemon=True).start()
    return srv.getsockname()[1]


def ok_reply(tid, unit, reg):
    return struct.pack('>HHHBBBH', tid, 0, 5, unit, 0x04, 2, 87)


def exc_reply(tid, unit, reg):
    return struct.pack('>HHHBBB', tid, 0, 3, unit, 0x84, 2)


ok_port = fake_server(ok_reply)
exc_port = fake_server(exc_reply)

r = probe('127.0.0.1', ok_port, 1)
assert r['ok'] and r['value'] == 87, r

r = probe('127.0.0.1', exc_port, 70000)  # transaction ID wraps to 16 bits
assert not r['ok'] and r['message'] == 'Modbus-fout 2 (Illegal data address)', r

r = probe('127.0.0.1', exc_port, 1, tcp_only=True)
assert r['ok'] and r['value'] is None, r

closed = socket.socket()
closed.bind(('127.0.0.1', 0))
closed_port = closed.getsockname()[1]
closed.close()
r = probe('127.0.0.1', closed_port, 1, timeout_ms=500)
assert not r['ok'] and r['message'], r

assert main(['127.0.0.1:{}'.format(ok_port), '-n', '2', '-i', '0']) == 0
assert main(['127.0.0.1:{}'.format(exc_port), '-n', '1']) == 1
assert main(['127.0.0.1:99999']) == 2
assert main(['127.0.0.1:502', '503']) == 2

print('\nOK')
