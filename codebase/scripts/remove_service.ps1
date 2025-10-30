param(
  [string]$ServiceName = "printer-system",
  [switch]$StopFirst = $true,
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

$nssm = Find-Nssm -Explicit $NssmPath

if ($StopFirst) {
  Write-Host "Stopping service '$ServiceName'..."
  & $nssm stop $ServiceName
}

Write-Host "Removing service '$ServiceName'..."
& $nssm remove $ServiceName confirm

if ($LASTEXITCODE -ne 0) {
  Write-Warning "Removal reported a non-zero exit ($LASTEXITCODE). Service may already be removed."
} else {
  Write-Host "Service '$ServiceName' removed."
}

