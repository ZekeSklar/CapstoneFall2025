param(
  [string]$ServiceName = "printer-system-dev"
)

function Remove-IfExists([string]$name){
  $t = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
  if ($t) {
    Unregister-ScheduledTask -TaskName $name -Confirm:$false | Out-Null
    Write-Host "Removed task: $name"
  }
}

$sumName = "$ServiceName - Daily Summary"
$preName = "$ServiceName - Prewarm Status"
Remove-IfExists -name $sumName
Remove-IfExists -name $preName
Write-Host "Done."

