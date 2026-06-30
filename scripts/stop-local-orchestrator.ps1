param()

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
$PidFile = Join-Path $ProjectRoot "work\orchestrator\local-web.pid"

if (-not (Test-Path $PidFile)) {
    Write-Host "No local orchestrator PID file found."
    exit 0
}

$RawPid = (Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
if (-not $RawPid) {
    Remove-Item -LiteralPath $PidFile -Force
    Write-Host "Empty PID file removed."
    exit 0
}

$Process = Get-Process -Id ([int]$RawPid) -ErrorAction SilentlyContinue
if (-not $Process) {
    Remove-Item -LiteralPath $PidFile -Force
    Write-Host "Local orchestrator was not running. PID file removed."
    exit 0
}

Stop-Process -Id $Process.Id -Force
Remove-Item -LiteralPath $PidFile -Force
Write-Host "Trading Bot Orchestrator stopped. PID: $($Process.Id)"

