param(
  [string]$RepoPath,
  [string]$ServiceName = "printer-system-dev",
  [int]$Port = 8000,
  [string]$SummaryTime = "07:00",   # 24h format HH:MM local time
  [int]$PrewarmEveryMinutes = 30,
  [switch]$AsSystem = $false
)

function Write-Step($msg){ Write-Host ("[+] " + $msg) -ForegroundColor Cyan }
function Stop-Error($msg){ Write-Error $msg; exit 1 }

function Resolve-RepoPath {
  if ($RepoPath) { return (Resolve-Path $RepoPath).Path }
  return (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}

function Find-VenvPython ([string]$Repo){
  $venvPython = Join-Path $Repo ".venv\Scripts\python.exe"
  if (-not (Test-Path $venvPython)) { Stop-Error ".venv not found. Run scripts\\bootstrap.ps1 first." }
  return $venvPython
}

function New-TaskUserParam {
  param([switch]$AsSystem)
  if ($AsSystem) { return @{ User = 'SYSTEM' } }
  else { return @{ User = $env:UserName } }
}

$repo = Resolve-RepoPath
$py = Find-VenvPython -Repo $repo

# --- Daily summary task ---
$sumName = "$ServiceName - Daily Summary"
$sumTime = [DateTime]::Parse($SummaryTime)
$sumTrigger = New-ScheduledTaskTrigger -Daily -At $sumTime.TimeOfDay
$sumAction = New-ScheduledTaskAction -Execute $py -Argument "manage.py send_issue_summary" -WorkingDirectory $repo
Write-Step "Registering task: $sumName at $SummaryTime"
Register-ScheduledTask -TaskName $sumName -Action $sumAction -Trigger $sumTrigger -Description "Send printer issue summary" -RunLevel Highest @((New-TaskUserParam -AsSystem:$AsSystem)) | Out-Null

# --- Prewarm status task (repeating) ---
$preName = "$ServiceName - Prewarm Status"
# Start one minute from now, repeat every N minutes
$start = (Get-Date).AddMinutes(1)
$interval = New-TimeSpan -Minutes $PrewarmEveryMinutes
$duration = New-TimeSpan -Days 365
$preTrigger = New-ScheduledTaskTrigger -Once -At $start -RepetitionInterval $interval -RepetitionDuration $duration
$preAction = New-ScheduledTaskAction -Execute $py -Argument "manage.py prewarm_status --force" -WorkingDirectory $repo
Write-Step "Registering task: $preName every $PrewarmEveryMinutes min (starts $($start.ToShortTimeString()))"
Register-ScheduledTask -TaskName $preName -Action $preAction -Trigger $preTrigger -Description "Prewarm SNMP status cache" -RunLevel Highest @((New-TaskUserParam -AsSystem:$AsSystem)) | Out-Null

Write-Host "Scheduled tasks created: `n - $sumName `n - $preName" -ForegroundColor Green

