param(
    [string]$Config = "config/bot.sample.toml",
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8000,
    [int]$IntervalSeconds = 30,
    [int]$MaxChecks = 0,
    [string]$PythonPath = ""
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
$StartScript = Join-Path $ScriptDir "start-local-orchestrator.ps1"
$WorkDir = Join-Path $ProjectRoot "work\orchestrator"
$LogFile = Join-Path $WorkDir "watchdog.log"
$Url = "http://${HostName}:${Port}/api/status"

New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null

function Write-WatchdogLog {
    param([string]$Message)

    $Stamp = (Get-Date).ToString("s")
    $Line = "[$Stamp] $Message"
    Add-Content -Path $LogFile -Value $Line -Encoding ASCII
    Write-Host $Line
}

function Test-OrchestratorHealth {
    try {
        $Response = Invoke-RestMethod -Uri $Url -TimeoutSec 3
        return [bool]$Response.mode
    } catch {
        return $false
    }
}

function Start-OrchestratorHidden {
    $Args = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $StartScript,
        "-Config", $Config,
        "-HostName", $HostName,
        "-Port", [string]$Port,
        "-NoBrowser"
    )

    if ($PythonPath) {
        $Args += @("-PythonPath", $PythonPath)
    }

    $Process = Start-Process -FilePath "powershell.exe" -ArgumentList $Args -WorkingDirectory $ProjectRoot -WindowStyle Hidden -PassThru
    Write-WatchdogLog "start requested pid=$($Process.Id)"
}

$Checks = 0
do {
    $Checks += 1
    if (Test-OrchestratorHealth) {
        Write-WatchdogLog "healthy url=$Url"
    } else {
        Write-WatchdogLog "not healthy, starting local orchestrator"
        Start-OrchestratorHidden
        Start-Sleep -Seconds 3
        if (Test-OrchestratorHealth) {
            Write-WatchdogLog "recovered url=http://${HostName}:${Port}/"
        } else {
            Write-WatchdogLog "still not healthy after start request"
        }
    }

    if ($MaxChecks -gt 0 -and $Checks -ge $MaxChecks) {
        break
    }

    Start-Sleep -Seconds $IntervalSeconds
} while ($true)
