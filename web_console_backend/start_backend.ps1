$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv-web\Scripts\python.exe"

if (-not (Test-Path $python)) {
  throw "Missing Python runtime: $python"
}

Set-Location $root
& $python -m uvicorn web_console_backend.app.main:app --host 127.0.0.1 --port 8765
