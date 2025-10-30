param(
  [string]$ServiceName = "printer-system",
  [string]$RepoPath,
  [int]$Port = 8000,
  [string]$NssmPath
)

function Find-Nssm {
  param([string]$Explicit)
  if ($Explicit -and (Test-Path $Explicit)) { return (Resolve-Path $Explicit).Path }
  $candidates = @(
    'nssm',
    'C:\Program Files\nssm\win64\nssm.exe',
    'C:\Program Files\nssm\win32\nssm.exe',
    'C:\Program Files\nssm-2.24\win64\nssm.exe',
    'C:\Program Files\nssm-2.24\win32\nssm.exe'
  )
  foreach ($p in $candidates) {
    try {
      $cmd = (Get-Command $p -ErrorAction SilentlyContinue)
      if ($cmd) { return $cmd.Source }
    } catch {}
    if (Test-Path $p) { return $p }
  }
  throw "Could not find NSSM. Install from https://nssm.cc/download or pass -NssmPath."
}

if (-not $RepoPath) {
  # Default to repo root (one directory up from scripts/)
  $RepoPath = Resolve-Path (Join-Path $PSScriptRoot '..')
}

$nssm = Find-Nssm -Explicit $NssmPath
$exe  = Join-Path $RepoPath '.venv\Scripts\waitress-serve.exe'
if (-not (Test-Path $exe)) { throw "App server not found: $exe. Create the venv and install requirements first." }

$args = "--listen=0.0.0.0:$Port printer_system.wsgi:application"

# Ensure data/ exists for logs
$dataDir = Join-Path $RepoPath 'data'
if (-not (Test-Path $dataDir)) { New-Item -ItemType Directory -Path $dataDir | Out-Null }
$stdout = Join-Path $dataDir 'service-stdout.log'
$stderr = Join-Path $dataDir 'service-stderr.log'

Write-Host "Installing service '$ServiceName' using NSSM: $nssm"
& $nssm install $ServiceName $exe $args
if ($LASTEXITCODE -ne 0) { throw "nssm install failed ($LASTEXITCODE)" }

& $nssm set $ServiceName AppDirectory $RepoPath
& $nssm set $ServiceName AppEnvironmentExtra "DJANGO_SETTINGS_MODULE=printer_system.settings"
& $nssm set $ServiceName AppEnvironmentExtra "PYTHONUNBUFFERED=1"
& $nssm set $ServiceName Start SERVICE_AUTO_START
& $nssm set $ServiceName AppStdout $stdout
& $nssm set $ServiceName AppStderr $stderr
& $nssm set $ServiceName AppRotateFiles 1
& $nssm set $ServiceName AppRotateBytes 10485760
& $nssm set $ServiceName AppRotateOnline 1

Write-Host "Starting service '$ServiceName'..."
& $nssm start $ServiceName
if ($LASTEXITCODE -ne 0) { throw "nssm start failed ($LASTEXITCODE)" }

Write-Host "Service '$ServiceName' installed and started. Listening on port $Port."

