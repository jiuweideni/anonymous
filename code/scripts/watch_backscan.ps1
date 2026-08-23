param(
    [string]$Config = "config_polygon_upgrade_100k.json",
    [int]$IntervalHours = 24,
    [int]$IntervalMinutes = 0,
    [string]$LogPath = "data_polygon_upgrade_100k\backscan\watch_backscan.log"
)

Set-Location (Split-Path -Parent $PSScriptRoot)
$sleepSeconds = if ($IntervalMinutes -gt 0) { $IntervalMinutes * 60 } else { $IntervalHours * 3600 }
$logDir = Split-Path -Parent $LogPath
if ($logDir -and -not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
}

while ($true) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$timestamp] Running resumable backscan..." | Tee-Object -FilePath $LogPath -Append
    & cmd.exe /c "python -m aa_auth_lifecycle.cli backscan --config $Config 2>&1" | Tee-Object -FilePath $LogPath -Append

    $cfg = Get-Content $Config -Raw | ConvertFrom-Json
    $statePath = Join-Path $cfg.output_dir "backscan\backscan_state.json"
    if (Test-Path $statePath) {
        $state = Get-Content $statePath -Raw | ConvertFrom-Json
        if ($state.status -eq "complete") {
            "Backscan complete." | Tee-Object -FilePath $LogPath -Append
            break
        }
    }

    "Sleeping for $sleepSeconds second(s) before retry..." | Tee-Object -FilePath $LogPath -Append
    Start-Sleep -Seconds $sleepSeconds
}
