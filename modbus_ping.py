#!/usr/bin/env python3
"""Ping-style connectivity test for a Modbus TCP device.

Each attempt opens a new TCP connection to the device and then reads 1 input register
(function code 04, read-only). Every attempt prints one line with the TCP time, the Modbus
time and the value read. At the end (or after Ctrl+C) statistics are shown, just like ping.

By default register 10014 is read: the state of charge (SOC, %) of an Anker SOLIX
Solarbank Max AC. The script never writes to the device.

Linux/macOS counterpart of Test-ModbusPing.ps1. Requires only Python 3.6+.
"""
import argparse
import re
import socket
import struct
import sys
import time

MODBUS_EXCEPTIONS = {
    1: 'Illegal function',
    2: 'Illegal data address',
    3: 'Illegal data value',
    4: 'Device failure',
    5: 'Acknowledge',
    6: 'Device busy',
    10: 'Gateway path unavailable',
    11: 'Gateway target did not respond',
}


def read_exact(sock, length):
    # Leest precies `length` bytes, of gooit een fout.
    buf = b''
    while len(buf) < length:
        chunk = sock.recv(length - len(buf))
        if not chunk:
            raise ConnectionError('Verbinding gesloten door het apparaat')
        buf += chunk
    return buf


def probe(host, port, sequence, timeout_ms=3000, unit_id=1, register=10014, tcp_only=False):
    """One attempt. Never raises; returns a dict with ok, tcp_ms, modbus_ms, value, message."""
    result = {'ok': False, 'tcp_ms': None, 'modbus_ms': None, 'value': None, 'message': ''}
    timeout = timeout_ms / 1000
    start = time.perf_counter()

    # 1. TCP-verbinding
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
    except socket.timeout:
        result['message'] = 'Time-out bij verbinden (TCP, {} ms)'.format(timeout_ms)
        return result
    except OSError as e:
        result['message'] = e.strerror or str(e)
        return result

    try:
        result['tcp_ms'] = round((time.perf_counter() - start) * 1000)
        if tcp_only:
            result['ok'] = True
            return result

        # 2. Modbus read input register (FC04), 1 register
        transaction_id = sequence & 0xFFFF
        request = struct.pack('>HHHBBHH', transaction_id, 0, 6, unit_id, 0x04, register, 1)

        modbus_start = time.perf_counter()
        sock.sendall(request)
        header = read_exact(sock, 7)
        response_id, _, length = struct.unpack('>HHH', header[:6])
        if length < 2 or length > 253:
            result['message'] = 'Ongeldig Modbus-antwoord (lengte {})'.format(length)
            return result
        pdu = read_exact(sock, length - 1)
        result['modbus_ms'] = round((time.perf_counter() - modbus_start) * 1000)

        if response_id != transaction_id:
            result['message'] = 'Transaction ID klopt niet (verwacht {}, kreeg {})'.format(
                transaction_id, response_id)
            return result

        function_code = pdu[0]
        if function_code & 0x80:
            code = pdu[1]
            text = MODBUS_EXCEPTIONS.get(code, 'Onbekende fout')
            result['message'] = 'Modbus-fout {} ({})'.format(code, text)
            return result
        if function_code != 0x04 or len(pdu) < 4:
            result['message'] = 'Onverwacht antwoord (function code {})'.format(function_code)
            return result

        result['value'] = (pdu[2] << 8) | pdu[3]
        result['ok'] = True
        return result
    except socket.timeout:
        result['message'] = 'Time-out bij wachten op Modbus-antwoord ({} ms)'.format(timeout_ms)
        return result
    except OSError as e:
        result['message'] = e.strerror or str(e)
        return result
    finally:
        sock.close()


def int_range(lo, hi):
    def check(text):
        value = int(text)
        if not lo <= value <= hi:
            raise argparse.ArgumentTypeError('must be between {} and {}'.format(lo, hi))
        return value
    return check


def float_range(lo, hi):
    def check(text):
        value = float(text)
        if not lo <= value <= hi:
            raise argparse.ArgumentTypeError('must be between {} and {}'.format(lo, hi))
        return value
    return check


def main(argv=None):
    p = argparse.ArgumentParser(
        description='Ping-style connectivity test for a Modbus TCP device (read-only, FC04).',
        epilog='Examples:\n'
               '  %(prog)s 192.168.4.166\n'
               '  %(prog)s 192.168.4.166 5020\n'
               '  %(prog)s 192.168.4.166:502 -t\n'
               '  %(prog)s 192.168.4.166 -n 20 -i 5 --tcp-only',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('target', help='IP address or hostname, may include the port: 192.168.4.166:502')
    p.add_argument('port', nargs='?', type=int_range(1, 65535),
                   help='Modbus TCP port (default 502)')
    p.add_argument('-n', '--count', type=int_range(1, 2**31 - 1), default=4,
                   help='number of attempts (default 4)')
    p.add_argument('-t', '--continuous', action='store_true', help='keep testing until Ctrl+C')
    p.add_argument('-w', '--timeout-ms', type=int_range(100, 60000), default=3000,
                   help='timeout per step in ms (default 3000)')
    p.add_argument('-i', '--interval', type=float_range(0, 3600), default=1.0,
                   help='wait time between attempts in seconds (default 1)')
    p.add_argument('--unit-id', type=int_range(0, 255), default=1,
                   help='Modbus unit ID (default 1, as used by the Home Assistant integration)')
    p.add_argument('--register', type=int_range(0, 65535), default=10014,
                   help='input register to read, FC04 (default 10014)')
    p.add_argument('--tcp-only', action='store_true',
                   help='only test the TCP connection, skip the Modbus read')
    args = p.parse_args(argv)

    host, port = args.target, args.port if args.port is not None else 502

    # Notatie "adres:poort" toestaan, zoals 192.168.4.166:502
    m = re.match(r'^([^:]+):(\d{1,5})$', args.target)
    if m:
        parsed_port = int(m.group(2))
        if not 1 <= parsed_port <= 65535:
            print("Ongeldige poort in '{}' (toegestaan: 1-65535).".format(args.target), file=sys.stderr)
            return 2
        if args.port is not None and args.port != parsed_port:
            print("Twee verschillende poorten opgegeven: {} in '{}' en {} via port.".format(
                parsed_port, args.target, args.port), file=sys.stderr)
            return 2
        host, port = m.group(1), parsed_port

    yellow, reset = ('\033[33m', '\033[0m') if sys.stdout.isatty() else ('', '')
    mode = 'alleen TCP' if args.tcp_only else 'Modbus FC04, unit {}, register {}'.format(
        args.unit_id, args.register)
    print()
    print('Modbus-ping naar {}:{} ({}):'.format(host, port, mode))

    sent = received = 0
    times = []
    try:
        sequence = 0
        while args.continuous or sequence < args.count:
            sequence += 1
            sent += 1
            r = probe(host, port, sequence, args.timeout_ms, args.unit_id, args.register,
                      args.tcp_only)
            stamp = time.strftime('%H:%M:%S')

            if r['ok']:
                received += 1
                if args.tcp_only:
                    times.append(r['tcp_ms'])
                    print('[{}] Antwoord van {}:{}: tcp={}ms'.format(stamp, host, port, r['tcp_ms']))
                else:
                    times.append(r['tcp_ms'] + r['modbus_ms'])
                    print('[{}] Antwoord van {}:{}: tcp={}ms modbus={}ms reg {}={}'.format(
                        stamp, host, port, r['tcp_ms'], r['modbus_ms'], args.register, r['value']))
            else:
                print('{}[{}] Mislukt: {}{}'.format(yellow, stamp, r['message'], reset))
            sys.stdout.flush()

            if args.continuous or sequence < args.count:
                time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        # Draait ook na Ctrl+C
        lost = sent - received
        lost_pct = round(lost / sent * 100) if sent else 0
        print()
        print('Statistieken voor {}:{}:'.format(host, port))
        print('    Pogingen: verzonden = {}, ontvangen = {}, verloren = {} ({}% verlies)'.format(
            sent, received, lost, lost_pct))
        if times:
            print('Tijden (totaal per poging):')
            print('    Minimum = {}ms, Maximum = {}ms, Gemiddeld = {}ms'.format(
                min(times), max(times), round(sum(times) / len(times))))

    return 0 if sent > 0 and received == sent else 1


if __name__ == '__main__':
    sys.exit(main())
