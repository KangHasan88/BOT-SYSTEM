param(
    [string]$Config = "config/bot.sample.toml",
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8000,
    [string]$PythonPath = "",
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
$WorkDir = Join-Path $ProjectRoot "work\orchestrator"
$PidFile = Join-Path $WorkDir "local-web.pid"
$OutLog = Join-Path $WorkDir "local-web.out.log"
$ErrLog = Join-Path $WorkDir "local-web.err.log"
$Url = "http://${HostName}:${Port}/"

New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null

function Resolve-Python {
    param([string]$Requested)

    if ($Requested -and (Test-Path $Requested)) {
        return (Resolve-Path $Requested).Path
    }

    $Bundled = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    if (Test-Path $Bundled) {
        return $Bundled
    }

    $Command = Get-Command python -ErrorAction SilentlyContinue
    if ($Command) {
        return $Command.Source
    }

    throw "Python executable not found. Pass -PythonPath or install Python."
}

function Test-Server {
    param([string]$TargetUrl)

    try {
        Invoke-RestMethod -Uri ($TargetUrl.TrimEnd("/") + "/api/setup") -TimeoutSec 2 | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Get-ExistingProcess {
    if (-not (Test-Path $PidFile)) {
        return $null
    }

    $RawPid = (Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    if (-not $RawPid) {
        return $null
    }

    $Process = Get-Process -Id ([int]$RawPid) -ErrorAction SilentlyContinue
    return $Process
}

function Repair-ProcessPathEnvironment {
    $ProcessPath = [Environment]::GetEnvironmentVariable("Path", "Process")
    if (-not $ProcessPath) {
        $ProcessPath = [Environment]::GetEnvironmentVariable("PATH", "Process")
    }
    if ($ProcessPath) {
        [Environment]::SetEnvironmentVariable("PATH", $null, "Process")
        [Environment]::SetEnvironmentVariable("Path", $ProcessPath, "Process")
    }
}

$Existing = Get-ExistingProcess
if ($Existing -and (Test-Server $Url)) {
    Write-Host "Trading Bot Orchestrator is already running."
    Write-Host "URL: $Url"
    Write-Host "PID: $($Existing.Id)"
    if (-not $NoBrowser) {
        Start-Process $Url
    }
    exit 0
}

$Python = Resolve-Python $PythonPath
$ConfigPath = Join-Path $ProjectRoot $Config
if (-not (Test-Path $ConfigPath)) {
    throw "Config file not found: $ConfigPath"
}

$Args = @(
    "-m", "trading_bot.cli",
    "serve-orchestrator",
    "--config", $Config,
    "--host", $HostName,
    "--port", [string]$Port
)

Repair-ProcessPathEnvironment

$Process = Start-Process `
    -FilePath $Python `
    -ArgumentList $Args `
    -WorkingDirectory $ProjectRoot `
    -RedirectStandardOutput $OutLog `
    -RedirectStandardError $ErrLog `
    -WindowStyle Hidden `
    -PassThru

Set-Content -Path $PidFile -Value $Process.Id -Encoding ASCII

$Ready = $false
for ($Attempt = 0; $Attempt -lt 20; $Attempt++) {
    Start-Sleep -Milliseconds 500
    if (Test-Server $Url) {
        $Ready = $true
        break
    }
    if ($Process.HasExited) {
        break
    }
}

if (-not $Ready) {
    Write-Host "Trading Bot Orchestrator did not become ready."
    Write-Host "PID: $($Process.Id)"
    Write-Host "Error log: $ErrLog"
    if (Test-Path $ErrLog) {
        Get-Content $ErrLog -Tail 20
    }
    exit 1
}

Write-Host "Trading Bot Orchestrator started."
Write-Host "URL: $Url"
Write-Host "PID: $($Process.Id)"
Write-Host "Logs: $OutLog"

if (-not $NoBrowser) {
    Start-Process $Url
}
