# Stop anything listening on port 8000 (including orphaned uvicorn reload workers) and start fresh.
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

function Stop-PortListeners {
    param([int]$Port)
    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique |
        ForEach-Object {
            Write-Host "Stopping PID $_ on port $Port..."
            Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
        }
}

# Orphaned uvicorn --reload workers keep listening after the parent exits.
Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match 'multiprocessing\.spawn|uvicorn.*dashboard\.backend\.main' } |
    ForEach-Object {
        Write-Host "Stopping stale Python PID $($_.ProcessId): $($_.CommandLine.Substring(0, [Math]::Min(80, $_.CommandLine.Length)))..."
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

Stop-PortListeners -Port 8000
Start-Sleep -Seconds 2
Stop-PortListeners -Port 8000

Push-Location $repoRoot
Write-Host "Starting dashboard backend on http://127.0.0.1:8000 ..."
python -m uvicorn dashboard.backend.main:app --host 127.0.0.1 --port 8000
