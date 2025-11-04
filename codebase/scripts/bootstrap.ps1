param(
  [string]$RepoPath,
  [string]$ServiceName = "printer-system-dev",
  [int]$Port = 8000,
  [string]$PythonPath = "",
  [string]$NssmPath = "",
  [switch]$OpenFirewall = $true
)

function Write-Step($msg){ Write-Host ("[+] " + $msg) -ForegroundColor Cyan }
function Stop-Error($msg){ Write-Error $msg; exit 1 }

function Resolve-RepoPath {
  if ($RepoPath) { return (Resolve-Path $RepoPath).Path }
  return (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}

function Find-Python {
  param([string]$Explicit)
  if ($Explicit -and (Test-Path $Explicit)) { return (Resolve-Path $Explicit).Path }
  $candidates = @(
    "$PWD\.venv\Scripts\python.exe",
    "python",
    "py"
  )
  foreach ($p in $candidates) {
    try { $cmd = (Get-Command $p -ErrorAction SilentlyContinue) } catch { $cmd=$null }
    if ($cmd) { return $cmd.Source }
  }
  Stop-Error "Python not found. Install Python 3.11 and add to PATH."
}

function Run($exe, $args){
  Write-Host ("    > " + $exe + ' ' + ($args -join ' ')) -ForegroundColor DarkGray
  & $exe @args
  if ($LASTEXITCODE -ne 0) { Stop-Error "Command failed ($LASTEXITCODE): $exe $args" }
}

function Ensure-Venv {
  param([string]$Repo)
  $venvPython = Join-Path $Repo ".venv\Scripts\python.exe"
  if (-not (Test-Path $venvPython)) {
    Write-Step "Creating virtual environment (.venv)"
    Run (Find-Python $PythonPath) @('-m','venv', '.venv')
  }
  return $venvPython
}

function Ensure-EnvFile {
  param([string]$Repo)
  $envPath = Join-Path $Repo ".env"
  if (-not (Test-Path $envPath)) {
    Write-Step "Creating starter .env (edit values after bootstrap)"
    @(
      'DEBUG=false',
      "SECRET_KEY=$( [guid]::NewGuid().ToString() )",
      'ALLOWED_HOSTS=127.0.0.1,localhost',
      'EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend',
      '# EMAIL_HOST=smtp.gmail.com',
      '# EMAIL_PORT=587',
      '# EMAIL_USE_TLS=true',
      '# EMAIL_HOST_USER=you@example.com',
      '# EMAIL_HOST_PASSWORD=app-password',
      'DEFAULT_FROM_EMAIL=Printing Services <no-reply@example.com>',
      'EMAIL_TO=you@example.com',
      'SNMP_COMMUNITY=public',
      'SNMP_TIMEOUT=5',
      'SNMP_RETRIES=1',
      'SNMP_POLL_INTERVAL_SECONDS=300'
    ) | Set-Content -Path $envPath -Encoding UTF8
  }
}

function Setup-App {
  param([string]$Repo)
  $venvPython = Ensure-Venv -Repo $Repo
  $pip = $venvPython
  Write-Step "Upgrading pip and installing requirements"
  Run $pip @('-m','pip','install','--upgrade','pip')
  Run $pip @('-m','pip','install','-r','requirements.txt')

  Ensure-EnvFile -Repo $Repo

  Write-Step "Running migrations"
  Push-Location $Repo
  Run $venvPython @('manage.py','migrate')
  Write-Step "Collecting static files"
  Run $venvPython @('manage.py','collectstatic','--noinput')
  Pop-Location
}

function Open-FirewallRule {
  param([int]$Port,[string]$SvcName)
  try {
    $name = "$SvcName-$Port"
    if (-not (Get-NetFirewallRule -DisplayName $name -ErrorAction SilentlyContinue)) {
      Write-Step "Opening Windows Firewall for TCP port $Port"
      New-NetFirewallRule -DisplayName $name -Direction Inbound -Protocol TCP -LocalPort $Port -Action Allow | Out-Null
    }
  } catch { Write-Warning "Unable to create firewall rule: $_" }
}

# --- main ---
$repo = Resolve-RepoPath
Write-Step "Using repository path: $repo"
Push-Location $repo

Setup-App -Repo $repo

if ($OpenFirewall) { Open-FirewallRule -Port $Port -SvcName $ServiceName }

Write-Step "Installing Windows service via NSSM"
& (Join-Path $PSScriptRoot 'install_service.ps1') -ServiceName $ServiceName -RepoPath $repo -Port $Port -NssmPath $NssmPath -DisplayName "Printer System Dev"
if ($LASTEXITCODE -ne 0) { Stop-Error "install_service.ps1 failed ($LASTEXITCODE)" }

Write-Host "Bootstrap complete. Edit .env to adjust EMAIL_*/ALLOWED_HOSTS and restart the service if needed." -ForegroundColor Green
Pop-Location
