# Test-ModbusPing

A `ping`-style connectivity test for Modbus TCP devices, in two versions:

| Platform | Script | Needs |
|---|---|---|
| Windows | `Test-ModbusPing.ps1` | Windows PowerShell 5.1 or PowerShell 7+ |
| Linux (Debian, Raspberry Pi OS, …) | `modbus_ping.py` | Python 3.6+ (no extra packages) |

Each attempt opens a new TCP connection and reads one input register (function code 04). Every attempt prints one line showing the TCP connect time, the Modbus response time and the value it read. When the run ends, or after Ctrl+C, you get ping-style statistics. Both versions give the same output and exit codes.

By default it reads register **10014**, the state of charge (SOC, %) of an **Anker SOLIX Solarbank Max AC**, using unit ID 1.

> The scripts are read-only. They only send FC04 requests and never write to the device.

## Download

### Linux

Just the script:

```bash
curl -fsSLO https://raw.githubusercontent.com/nomnomnomnl/Script-Test-ModbusPing/main/modbus_ping.py
chmod +x modbus_ping.py
```

If `curl` is missing, use `wget https://raw.githubusercontent.com/nomnomnomnl/Script-Test-ModbusPing/main/modbus_ping.py` instead. Debian and Raspberry Pi OS normally ship with Python 3; if not, run `sudo apt install python3`.

Or the whole repository:

```bash
git clone https://github.com/nomnomnomnl/Script-Test-ModbusPing.git
cd Script-Test-ModbusPing
```

### Windows

Just the script (PowerShell):

```powershell
Invoke-WebRequest https://raw.githubusercontent.com/nomnomnomnl/Script-Test-ModbusPing/main/Test-ModbusPing.ps1 -OutFile Test-ModbusPing.ps1
Unblock-File .\Test-ModbusPing.ps1
```

Or the whole repository: `git clone https://github.com/nomnomnomnl/Script-Test-ModbusPing.git`, or **Code → Download ZIP** on GitHub.

The device needs to be reachable on its Modbus TCP port (default 502).

## Usage

**Linux**

```bash
./modbus_ping.py 192.168.4.166                 # 4 attempts on port 502
./modbus_ping.py 192.168.4.166 5020            # different port
./modbus_ping.py 192.168.4.166:502 -t          # continuous until Ctrl+C
./modbus_ping.py 192.168.4.166 -n 20 -i 5 --tcp-only
./modbus_ping.py -h                            # full help
```

**Windows**

```powershell
.\Test-ModbusPing.ps1 192.168.4.166                 # 4 attempts on port 502
.\Test-ModbusPing.ps1 192.168.4.166 5020            # different port
.\Test-ModbusPing.ps1 192.168.4.166:502 -t          # continuous until Ctrl+C
.\Test-ModbusPing.ps1 192.168.4.166 -n 20 -i 5 -TcpOnly
Get-Help .\Test-ModbusPing.ps1 -Full                # full help
```

If script execution is blocked on Windows, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\Test-ModbusPing.ps1 192.168.4.166
```

### Anker SOLIX Solarbank Max AC

The defaults are set for this device, so all you need is its IP address:

```bash
./modbus_ping.py 192.168.4.166          # Linux
.\Test-ModbusPing.ps1 192.168.4.166     # Windows
```

This reads input register 10014 (SOC, %) with unit ID 1, the same unit ID the Home Assistant integration uses. If you get a reply such as `reg 10014=87`, both the TCP connection and the Modbus communication are working.

### Other Modbus devices

Register 10014 is specific to the Anker. On other devices, start with the TCP-only mode: it only checks that the Modbus port accepts connections and sends no Modbus request at all.

```bash
./modbus_ping.py 192.168.1.50 --tcp-only                 # Linux
./modbus_ping.py 192.168.1.50:5020 --tcp-only -t
.\Test-ModbusPing.ps1 192.168.1.50 -TcpOnly              # Windows
.\Test-ModbusPing.ps1 192.168.1.50:5020 -TcpOnly -t
```

If you know a valid input register for the device, you can test the full Modbus read too:

```bash
./modbus_ping.py 192.168.1.50 --unit-id 3 --register 0          # Linux
.\Test-ModbusPing.ps1 192.168.1.50 -UnitId 3 -Register 0        # Windows
```

The register is the raw protocol address, which starts at 0. Many manuals list input registers in 3xxxx notation, where `30001` usually means address `0`.

A reply of `Modbus-fout 2 (Illegal data address)` means the connection works but the device doesn't have that register.

### Options

| Linux (`modbus_ping.py`) | Windows (`Test-ModbusPing.ps1`) | Default | Description |
|---|---|---|---|
| `target` | `-Target` | (required) | IP or hostname, optionally `host:port` |
| `port` (2nd argument) | `-Port` | `502` | Modbus TCP port |
| `-n`, `--count` | `-n`, `-Count` | `4` | Number of attempts |
| `-t`, `--continuous` | `-t`, `-Continuous` | | Keep going until Ctrl+C |
| `-w`, `--timeout-ms` | `-w`, `-TimeoutMs` | `3000` | Timeout per step (ms) |
| `-i`, `--interval` | `-i`, `-IntervalSeconds` | `1` | Pause between attempts (s) |
| `--unit-id` | `-UnitId` | `1` | Modbus unit ID |
| `--register` | `-Register` | `10014` | Input register to read (FC04) |
| `--tcp-only` | `-TcpOnly` | | Only test the TCP connection |

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

## Self-check

`test_modbus_ping.py` tests the Python version against a fake Modbus server on localhost. It needs no device:

```bash
python3 test_modbus_ping.py
```
