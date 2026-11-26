<#
.SYNOPSIS
    Ping-style connectivity test for a Modbus TCP device.

.DESCRIPTION
    Each attempt opens a new TCP connection to the device and then reads 1 input register
    (function code 04, read-only). Every attempt prints one line with the TCP time, the Modbus time
    and the value read. At the end (or after Ctrl+C) statistics are shown, just like ping.

    By default register 10014 is read: the state of charge (SOC, %) of an Anker SOLIX
    Solarbank Max AC. The script never writes to the device.

.PARAMETER Target
    IP address or hostname of the device (required). May include the port: 192.168.4.166:502.

.PARAMETER Port
    Modbus TCP port (second position). Defaults to 502.

.PARAMETER Count
    Number of attempts (alias -n). Defaults to 4, like ping.

.PARAMETER Continuous
    Keep testing until Ctrl+C (alias -t).

.PARAMETER TimeoutMs
    Timeout per step in milliseconds (alias -w).

.PARAMETER IntervalSeconds
    Wait time between attempts in seconds (alias -i).

.PARAMETER UnitId
    Modbus unit ID. The Home Assistant integration uses 1.

.PARAMETER Register
    Input register to read (function code 04).

.PARAMETER TcpOnly
    Only test the TCP connection, skip the Modbus read.

.EXAMPLE
    .\Test-ModbusPing.ps1 192.168.4.166
    Four attempts to 192.168.4.166 on port 502, reads the SOC.

.EXAMPLE
    .\Test-ModbusPing.ps1 192.168.4.166 5020
    Same, but on port 5020.

.EXAMPLE
    .\Test-ModbusPing.ps1 192.168.4.166:502 -t
    IP and port in one go, test continuously until Ctrl+C.

.EXAMPLE
    .\Test-ModbusPing.ps1 -Target 192.168.4.166 -Port 502 -n 20 -i 5 -TcpOnly
    Test only the TCP port twenty times, every 5 seconds.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0,
        HelpMessage = 'IP-adres of hostnaam, eventueel met poort (bijv. 192.168.4.166:502)')]
    [ValidateNotNullOrEmpty()]
    [string]$Target,

    [Parameter(Position = 1)]
    [ValidateRange(1, 65535)]
    [int]$Port = 502,

    [Alias('n')]
    [ValidateRange(1, [int]::MaxValue)]
    [int]$Count = 4,

    [Alias('t')]
    [switch]$Continuous,

    [Alias('w')]
    [ValidateRange(100, 60000)]
    [int]$TimeoutMs = 3000,

    [Alias('i')]
    [ValidateRange(0, 3600)]
    [double]$IntervalSeconds = 1,

    [ValidateRange(0, 255)]
    [int]$UnitId = 1,

    [ValidateRange(0, 65535)]
    [int]$Register = 10014,

    [switch]$TcpOnly
)

# Notatie "adres:poort" toestaan, zoals 192.168.4.166:502
if ($Target -match '^(?<addr>[^:]+):(?<prt>\d{1,5})$') {
    $parsedPort = [int]$Matches['prt']
    if ($parsedPort -lt 1 -or $parsedPort -gt 65535) {
        Write-Error "Ongeldige poort in '$Target' (toegestaan: 1-65535)."
        exit 2
    }
    if ($PSBoundParameters.ContainsKey('Port') -and $Port -ne $parsedPort) {
        Write-Error "Twee verschillende poorten opgegeven: $parsedPort in '$Target' en $Port via -Port."
        exit 2
    }
    $Target = $Matches['addr']
    $Port = $parsedPort
}

$ModbusExceptions = @{
    1  = 'Illegal function'
    2  = 'Illegal data address'
    3  = 'Illegal data value'
    4  = 'Device failure'
    5  = 'Acknowledge'
    6  = 'Device busy'
    10 = 'Gateway path unavailable'
    11 = 'Gateway target did not respond'
}

function Get-InnermostMessage {
    param([System.Exception]$Exception)
    $e = $Exception
    while ($null -ne $e.InnerException) { $e = $e.InnerException }
    return $e.Message
}

function Read-Exact {
    # Leest precies $Length bytes van de stream, of gooit een fout.
    param([System.Net.Sockets.NetworkStream]$Stream, [int]$Length)
    $buffer = New-Object byte[] $Length
    $offset = 0
    while ($offset -lt $Length) {
        $read = $Stream.Read($buffer, $offset, $Length - $offset)
        if ($read -le 0) { throw 'Verbinding gesloten door het apparaat' }
        $offset += $read
    }
    return , $buffer
}

function Invoke-ModbusProbe {
    param([int]$Sequence)

    $result = [pscustomobject]@{
        Ok       = $false
        TcpMs    = $null
        ModbusMs = $null
        Value    = $null
        Message  = ''
    }

    $client = New-Object System.Net.Sockets.TcpClient
    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        # 1. TCP-verbinding
        $connect = $client.ConnectAsync($Target, $Port)
        if (-not $connect.Wait($TimeoutMs)) {
            $result.Message = "Time-out bij verbinden (TCP, $TimeoutMs ms)"
            return $result
        }
        $result.TcpMs = [math]::Round($stopwatch.Elapsed.TotalMilliseconds)

        if ($TcpOnly) {
            $result.Ok = $true
            return $result
        }

        # 2. Modbus read input register (FC04), 1 register
        $stream = $client.GetStream()
        $stream.ReadTimeout = $TimeoutMs
        $stream.WriteTimeout = $TimeoutMs

        $transactionId = $Sequence -band 0xFFFF
        $request = [byte[]]@(
            (($transactionId -shr 8) -band 0xFF), ($transactionId -band 0xFF),  # transaction ID
            0, 0,                                                               # protocol ID
            0, 6,                                                               # lengte rest van frame
            $UnitId,                                                            # unit ID
            0x04,                                                               # function code 04
            (($Register -shr 8) -band 0xFF), ($Register -band 0xFF),            # startadres
            0, 1                                                                # aantal registers
        )

        $modbusStart = $stopwatch.Elapsed.TotalMilliseconds
        $stream.Write($request, 0, $request.Length)

        $header = Read-Exact -Stream $stream -Length 7
        $length = ($header[4] * 256) + $header[5]
        if ($length -lt 2 -or $length -gt 253) {
            $result.Message = "Ongeldig Modbus-antwoord (lengte $length)"
            return $result
        }
        $pdu = Read-Exact -Stream $stream -Length ($length - 1)
        $result.ModbusMs = [math]::Round($stopwatch.Elapsed.TotalMilliseconds - $modbusStart)

        $responseId = ($header[0] * 256) + $header[1]
        if ($responseId -ne $transactionId) {
            $result.Message = "Transaction ID klopt niet (verwacht $transactionId, kreeg $responseId)"
            return $result
        }

        $functionCode = $pdu[0]
        if ($functionCode -band 0x80) {
            $code = [int]$pdu[1]
            $text = $ModbusExceptions[$code]
            if (-not $text) { $text = 'Onbekende fout' }
            $result.Message = "Modbus-fout $code ($text)"
            return $result
        }
        if ($functionCode -ne 0x04 -or $pdu.Length -lt 4) {
            $result.Message = "Onverwacht antwoord (function code $functionCode)"
            return $result
        }

        $result.Value = ($pdu[2] * 256) + $pdu[3]
        $result.Ok = $true
        return $result
    }
    catch {
        $result.Message = Get-InnermostMessage $_.Exception
        return $result
    }
    finally {
        $client.Close()
    }
}

# ---------------------------------------------------------------------------

$mode = if ($TcpOnly) { 'alleen TCP' } else { "Modbus FC04, unit $UnitId, register $Register" }
Write-Host ''
Write-Host "Modbus-ping naar ${Target}:$Port ($mode):"

$sent = 0
$received = 0
$times = New-Object System.Collections.Generic.List[double]

try {
    $sequence = 0
    while ($Continuous -or $sequence -lt $Count) {
        $sequence++
        $sent++
        $probe = Invoke-ModbusProbe -Sequence $sequence
        $stamp = Get-Date -Format 'HH:mm:ss'

        if ($probe.Ok) {
            $received++
            if ($TcpOnly) {
                $times.Add($probe.TcpMs)
                Write-Host ("[{0}] Antwoord van {1}:{2}: tcp={3}ms" -f $stamp, $Target, $Port, $probe.TcpMs)
            }
            else {
                $total = $probe.TcpMs + $probe.ModbusMs
                $times.Add($total)
                Write-Host ("[{0}] Antwoord van {1}:{2}: tcp={3}ms modbus={4}ms reg {5}={6}" -f `
                        $stamp, $Target, $Port, $probe.TcpMs, $probe.ModbusMs, $Register, $probe.Value)
            }
        }
        else {
            Write-Host ("[{0}] Mislukt: {1}" -f $stamp, $probe.Message) -ForegroundColor Yellow
        }

        if ($Continuous -or $sequence -lt $Count) {
            Start-Sleep -Milliseconds ([int]($IntervalSeconds * 1000))
        }
    }
}
finally {
    # Draait ook na Ctrl+C
    $lost = $sent - $received
    $lostPct = 0
    if ($sent -gt 0) { $lostPct = [math]::Round(($lost / $sent) * 100) }

    Write-Host ''
    Write-Host "Statistieken voor ${Target}:${Port}:"
    Write-Host ("    Pogingen: verzonden = {0}, ontvangen = {1}, verloren = {2} ({3}% verlies)" -f `
            $sent, $received, $lost, $lostPct)
    if ($times.Count -gt 0) {
        $stats = $times | Measure-Object -Minimum -Maximum -Average
        Write-Host 'Tijden (totaal per poging):'
        Write-Host ("    Minimum = {0}ms, Maximum = {1}ms, Gemiddeld = {2}ms" -f `
                $stats.Minimum, $stats.Maximum, [math]::Round($stats.Average))
    }
}

if ($sent -gt 0 -and $received -eq $sent) { exit 0 } else { exit 1 }
