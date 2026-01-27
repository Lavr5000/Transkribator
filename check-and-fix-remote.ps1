# Check and Fix Remote Transcriber Server
# Check remote server health and suggest fix

$ErrorActionPreference = "Continue"

Write-Host "=== Remote Transcriber Server Check ===" -ForegroundColor Cyan
Write-Host ""

$tailserver = "http://100.102.178.110:8000"
$serveoUrl = "http://elated-dhawan-remote.serveo.net:8000"

# 1. Check Tailscale
Write-Host "[1] Checking Tailscale connection..." -ForegroundColor Yellow
try {
    $ping = Test-Connection -ComputerName 100.102.178.110 -Count 1 -Quiet
    if ($ping) {
        Write-Host "    Tailscale: Online" -ForegroundColor Green
    } else {
        Write-Host "    Tailscale: Offline" -ForegroundColor Red
    }
} catch {
    Write-Host "    Tailscale: Not available" -ForegroundColor Red
}

# 2. Check health endpoint
Write-Host "[2] Checking health endpoint..." -ForegroundColor Yellow
$serverHealthy = $false
try {
    $response = Invoke-RestMethod -Uri "$tailserver/health" -TimeoutSec 3
    Write-Host "    Server: Healthy!" -ForegroundColor Green
    Write-Host "    Status: $($response.status)" -ForegroundColor Gray
    Write-Host "    Loaded: $($response.transcriber_loaded)" -ForegroundColor Gray
    $serverHealthy = $true
} catch {
    Write-Host "    Server: Not responding" -ForegroundColor Red
    Write-Host "    Error: $($_.Exception.Message)" -ForegroundColor DarkGray
}

# 3. Result
Write-Host ""
if ($serverHealthy) {
    Write-Host "=== SERVER WORKING! ===" -ForegroundColor Green
    Write-Host "Transcriber should use remote PC." -ForegroundColor Cyan
} else {
    Write-Host "=== SERVER NOT WORKING ===" -ForegroundColor Red
    Write-Host ""
    Write-Host "Cause: Server running on 127.0.0.1 instead of 0.0.0.0" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "1. Connect to remote PC via RDP (IP: 100.102.178.110)" -ForegroundColor White
    Write-Host "2. Open file:" -ForegroundColor White
    Write-Host "   C:\Users\user\.claude\0 ProEKTi\Transkribator\TranscriberServer\AUTOSTART_SERVEO_UPDATED.bat" -ForegroundColor DarkYellow
    Write-Host "3. Change line 19:" -ForegroundColor White
    Write-Host "   --host 127.0.0.1" -ForegroundColor Red
    Write-Host "   to:" -ForegroundColor White
    Write-Host "   --host 0.0.0.0" -ForegroundColor Green
    Write-Host "4. Restart server" -ForegroundColor White
    Write-Host ""
    Write-Host "Full instructions: .\APPLY-FIX-REMOTE.md" -ForegroundColor Cyan
}

Write-Host ""
