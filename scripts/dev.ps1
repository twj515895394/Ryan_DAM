# Ryan_DAM dev-mode launcher.
# Resolves the repo root from this file's location, verifies the venv and
# node_modules, refuses to start when port 5173 is already taken (a stale
# vite would make dev:electron attach to old code), then runs `npm run dev`.
param(
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

Write-Host "Ryan_DAM dev launcher" -ForegroundColor Cyan
Write-Host "  repo: $root"

$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "[X] .venv not found at $venvPython" -ForegroundColor Red
    Write-Host "    Create it first:" -ForegroundColor Red
    Write-Host "      py -3.12 -m venv .venv" -ForegroundColor Red
    Write-Host "      .\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt" -ForegroundColor Red
    exit 1
}
Write-Host "  [OK] venv python" -ForegroundColor Green

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host "[X] npm not on PATH - install Node.js 22+ first" -ForegroundColor Red
    exit 1
}

$nodeModules = Join-Path $root "node_modules"
if (-not (Test-Path $nodeModules)) {
    Write-Host "[X] node_modules missing - run: npm install" -ForegroundColor Red
    exit 1
}
Write-Host "  [OK] node_modules" -ForegroundColor Green

$listener = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    $ownerPid = ($listener | Select-Object -First 1).OwningProcess
    Write-Host "[X] port 5173 is already in use by PID $ownerPid" -ForegroundColor Red
    Write-Host "    A stale vite would feed OLD code to Electron. If it is a leftover," -ForegroundColor Red
    Write-Host "    stop it with:  taskkill /PID $ownerPid /F" -ForegroundColor Red
    exit 1
}
Write-Host "  [OK] port 5173 free" -ForegroundColor Green

if ($CheckOnly) {
    Write-Host "[OK] all checks passed (-CheckOnly, not starting)" -ForegroundColor Green
    exit 0
}

$env:RYAN_DAM_PYTHON = $venvPython
Write-Host "  RYAN_DAM_PYTHON = $env:RYAN_DAM_PYTHON"
Write-Host "Starting dev mode (vite + electron + backend)..." -ForegroundColor Cyan
Write-Host "Close the Electron window or press Ctrl+C to stop." -ForegroundColor DarkGray
Write-Host ""

Push-Location $root
try {
    npm run dev
}
finally {
    Pop-Location
}
