$ErrorActionPreference = "SilentlyContinue"

$processNames = @(
  "msedge.exe",
  "msedgewebview2.exe",
  "chrome.exe"
)

foreach ($name in $processNames) {
  taskkill /IM $name /F /T | Out-Null
  if ($LASTEXITCODE -eq 0) {
    Write-Host "Stopped process tree: $name"
  } else {
    Write-Host "Process not running or could not be stopped: $name"
  }
}
