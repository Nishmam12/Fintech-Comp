# Reset the dashboard demo to a clean state for a (re)take. Run from the repo root in PowerShell:
#   powershell -ExecutionPolicy Bypass -File scripts\reset-demo.ps1
# Needs the API already running on port 8000 (BK_SETTLEMENT_MODE=simulated). It seeds a fresh mandate (new demo keys go to
# frontend/.env.local), restarts the dashboard on port 3000 so it picks the new keys up, and waits until the page answers.
# Prints no key. After it finishes, reload http://localhost:3000 and sign in with the buttons.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

try { (Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 10) | Out-Null }
catch { Write-Error "The API is not answering on port 8000. Start it first (see docs/demo/RECORDING_RUNBOOK.md)."; exit 1 }

Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue |
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2

Push-Location $root
uv run --project backend python scripts/demo_seed.py
Pop-Location

$front = Join-Path $root "frontend"
Remove-Item -Recurse -Force (Join-Path $front ".next") -ErrorAction SilentlyContinue
Start-Process -FilePath "npm.cmd" -ArgumentList "run", "dev" -WorkingDirectory $front -WindowStyle Hidden

for ($i = 0; $i -lt 60; $i++) {
  try { Invoke-WebRequest -Uri "http://localhost:3000" -UseBasicParsing -TimeoutSec 5 | Out-Null; Write-Host "Dashboard ready: http://localhost:3000"; exit 0 }
  catch { Start-Sleep -Seconds 3 }
}
Write-Error "The dashboard did not start within 3 minutes."; exit 1
