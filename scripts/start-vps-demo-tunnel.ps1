param(
    [string]$SshUser = "tradingbot",
    [string]$SshHost = "31.97.106.123",
    [int]$LocalPort = 18000,
    [int]$RemotePort = 8000
)

$ErrorActionPreference = "Stop"

Write-Host "Starting private VPS demo tunnel..."
Write-Host "Local URL:  http://127.0.0.1:$LocalPort/"
Write-Host "Remote URL: 127.0.0.1:$RemotePort on VPS"
Write-Host "Press Ctrl+C to stop the tunnel."

ssh -N -L "127.0.0.1:$LocalPort`:127.0.0.1:$RemotePort" "$SshUser@$SshHost"
