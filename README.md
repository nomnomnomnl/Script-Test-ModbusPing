# Test-ModbusPing

A `ping`-style connectivity test for Modbus TCP devices. It comes in two versions: PowerShell for Windows (`Test-ModbusPing.ps1`) and Python 3 for Linux (`modbus_ping.py`, see [Linux](#linux-debian-raspberry-pi-os-)).

Each attempt opens a new TCP connection and reads one input register (function code 04). Every attempt prints one line showing the TCP connect time, the Modbus response time and the value it read. When the run ends, or after Ctrl+C, you get ping-style statistics.

By default it reads register **10014**, the state of charge (SOC, %) of an **Anker SOLIX Solarbank Max AC**, using unit ID 1. You can read a different register with `-Register`.

> The script is read-only. It only sends FC04 requests and never writes to the device.

## Requirements

- Windows PowerShell 5.1 or PowerShell 7+
- Network access to the device's Modbus TCP port (default 502)

## Usage

```powershell
.\Test-ModbusPing.ps1 192.168.4.166                 # 4 attempts on port 502
.\Test-ModbusPing.ps1 192.168.4.166 5020            # different port
.\Test-ModbusPing.ps1 192.168.4.166:502 -t          # continuous until Ctrl+C
.\Test-ModbusPing.ps1 192.168.4.166 -n 20 -i 5 -TcpOnly
```

If script execution is blocked, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\Test-ModbusPing.ps1 192.168.4.166
```

### Anker SOLIX Solarbank Max AC

The defaults are set for this device, so all you need is its IP address:

```powershell
.\Test-ModbusPing.ps1 192.168.4.166
```

This reads input register 10014 (SOC, %) with unit ID 1, the same unit ID the Home Assistant integration uses. If you get a reply such as `reg 10014=87`, both the TCP connection and the Modbus communication are working.

### Other Modbus devices

Register 10014 is specific to the Anker. On other devices, start with `-TcpOnly`: it only checks that the Modbus port accepts connections and sends no Modbus request at all.

```powershell
.\Test-ModbusPing.ps1 192.168.1.50 -TcpOnly
.\Test-ModbusPing.ps1 192.168.1.50:5020 -TcpOnly -t
```

If you know a valid input register for the device, you can test the full Modbus read too:

```powershell
.\Test-ModbusPing.ps1 192.168.1.50 -UnitId 3 -Register 0
```

`-Register` expects the raw protocol address, which starts at 0. Many manuals list input registers in 3xxxx notation, where `30001` usually means address `0`.

A reply of `Modbus-fout 2 (Illegal data address)` means the connection works but the device doesn't have that register.

### Parameters

| Parameter | Alias | Default | Description |
|---|---|---|---|
| `Target` | | (required) | IP or hostname, optionally `host:port` |
| `Port` | | `502` | Modbus TCP port |
| `Count` | `-n` | `4` | Number of attempts |
| `Continuous` | `-t` | | Keep going until Ctrl+C |
| `TimeoutMs` | `-w` | `3000` | Timeout per step (ms) |
| `IntervalSeconds` | `-i` | `1` | Pause between attempts (s) |
| `UnitId` | | `1` | Modbus unit ID |
| `Register` | | `10014` | Input register to read (FC04) |
| `TcpOnly` | | | Only test the TCP connection |

Full help: `Get-Help .\Test-ModbusPing.ps1 -Full`

### Example output

```
Modbus-ping naar 192.168.4.166:502 (Modbus FC04, unit 1, register 10014):
[14:02:11] Antwoord van 192.168.4.166:502: tcp=4ms modbus=38ms reg 10014=87
[14:02:12] Antwoord van 192.168.4.166:502: tcp=3ms modbus=41ms reg 10014=87
[14:02:13] Mislukt: Time-out bij verbinden (TCP, 3000 ms)
[14:02:17] Antwoord van 192.168.4.166:502: tcp=5ms modbus=36ms reg 10014=87

Statistieken voor 192.168.4.166:502:
    Pogingen: verzonden = 4, ontvangen = 3, verloren = 1 (25% verlies)
Tijden (totaal per poging):
    Minimum = 41ms, Maximum = 44ms, Gemiddeld = 42ms
```

Console output is in Dutch.

### Exit codes

| Code | Meaning |
|---|---|
| `0` | All attempts succeeded |
| `1` | One or more attempts failed |
| `2` | Invalid or conflicting port in `host:port` |

## Linux (Debian, Raspberry Pi OS, …)

`modbus_ping.py` works the same way as the PowerShell version and prints the same output and exit codes. It needs Python 3.6+ and nothing else; Debian and Raspberry Pi OS normally ship with Python 3.

```bash
chmod +x modbus_ping.py
./modbus_ping.py 192.168.4.166                 # Anker, 4 attempts on port 502
./modbus_ping.py 192.168.4.166:502 -t          # continuous until Ctrl+C
./modbus_ping.py 192.168.1.50 --tcp-only       # other Modbus devices
./modbus_ping.py 192.168.1.50 --unit-id 3 --register 0
./modbus_ping.py -h                            # full help
```

The short options match the PowerShell aliases. The long ones are written in Linux style:

| PowerShell | Python |
|---|---|
| `-Port` | second positional argument |
| `-Count` / `-n` | `--count` / `-n` |
| `-Continuous` / `-t` | `--continuous` / `-t` |
| `-TimeoutMs` / `-w` | `--timeout-ms` / `-w` |
| `-IntervalSeconds` / `-i` | `--interval` / `-i` |
| `-UnitId` | `--unit-id` |
| `-Register` | `--register` |
| `-TcpOnly` | `--tcp-only` |

To check the script itself (uses a fake Modbus server on localhost):

```bash
python3 test_modbus_ping.py
```
