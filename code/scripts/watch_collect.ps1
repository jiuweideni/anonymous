param(
    [string]$Config = "config.json",
    [int]$IntervalHours = 24
)

Set-Location (Split-Path -Parent $PSScriptRoot)

while ($true) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] Running resumable collection..."
    python -m aa_auth_lifecycle.cli collect --config $Config
    python -m aa_auth_lifecycle.cli analyze --config $Config
    python -m aa_auth_lifecycle.cli report --config $Config

    $cfg = Get-Content $Config -Raw | ConvertFrom-Json
    $statePath = Join-Path $cfg.output_dir "collection_state.json"
    if (Test-Path $statePath) {
        $state = Get-Content $statePath -Raw | ConvertFrom-Json
        if ($state.status -eq "complete") {
            Write-Host "Collection complete."
            break
        }
    }

    Write-Host "Sleeping for $IntervalHours hour(s) before retry..."
    Start-Sleep -Seconds ($IntervalHours * 3600)
}
