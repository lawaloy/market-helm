# Start MarketHelm dev stack on alternate ports (backend 8001, frontend 3001).
# Use when 8000/3000 are stuck or serving a stale process.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host "Starting backend on http://127.0.0.1:8001 ..."
Start-Process -FilePath "python" `
  -ArgumentList "-m", "uvicorn", "dashboard.backend.main:app", "--host", "127.0.0.1", "--port", "8001" `
  -WorkingDirectory $Root `
  -WindowStyle Normal

Start-Sleep -Seconds 2

Write-Host "Starting frontend on http://localhost:3001 (API proxy -> 8001) ..."
Push-Location (Join-Path $Root "dashboard\frontend")
$env:VITE_DEV_PORT = "3001"
$env:VITE_DEV_API_TARGET = "http://127.0.0.1:8001"
npm run dev:3001
Pop-Location
