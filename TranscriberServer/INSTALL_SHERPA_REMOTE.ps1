# Remote Sherpa Installation Script
# Run this on LAPTOP - it will execute commands on remote PC via WinRM

$RemotePC = "192.168.31.9"
$RemoteUser = "192.168.31.9\Denis"
$RemotePath = "C:\Users\Denis\TranscriberServer"
$LocalSrc = "C:\Users\user\.claude\0 ProEKTi\Transkribator\src"

Write-Host "========================================"  -ForegroundColor Cyan
Write-Host "Remote Sherpa Installation"  -ForegroundColor Cyan
Write-Host "========================================"  -ForegroundColor Cyan
Write-Host ""

# Test WinRM connection
Write-Host "[1/7] Testing WinRM connection..." -ForegroundColor Yellow
try {
    Test-WSMan -ComputerName $RemotePC -ErrorAction Stop | Out-Null
    Write-Host "  OK: WinRM is accessible" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: WinRM not enabled on $RemotePC" -ForegroundColor Red
    Write-Host ""
    Write-Host "To enable WinRM on remote PC, run this ON REMOTE PC:" -ForegroundColor Yellow
    Write-Host "  winrm quickconfig" -ForegroundColor Cyan
    Write-Host ""
    pause
    exit 1
}

# Copy src folder using admin share
Write-Host "[2/7] Copying src folder..." -ForegroundColor Yellow
try {
    $DestPath = "\\$RemotePC\C$\Users\Denis\TranscriberServer\src"
    if (!(Test-Path $DestPath)) {
        New-Item -Path $DestPath -ItemType Directory -Force | Out-Null
    }

    # Use robocopy for reliable copy
    $Result = robocopy $LocalSrc $DestPath /E /R:1 /W:1 /NFL /NDL /NJH /NJS
    if ($LASTEXITCODE -lt 8) {
        Write-Host "  OK: src folder copied" -ForegroundColor Green
    } else {
        Write-Host "  WARNING: Copy had issues (code $LASTEXITCODE)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ERROR: $_" -ForegroundColor Red
}

# Install sherpa-onnx remotely
Write-Host "[3/7] Installing sherpa-onnx..." -ForegroundColor Yellow
try {
    $InstallScript = {
        param($Path)
        cd $Path
        pip install sherpa-onnx --quiet
    }
    Invoke-Command -ComputerName $RemotePC -ScriptBlock $InstallScript -ArgumentList $RemotePath -ErrorAction Stop
    Write-Host "  OK: sherpa-onnx installed" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: $_" -ForegroundColor Red
    Write-Host "  You may need to install manually: pip install sherpa-onnx" -ForegroundColor Yellow
}

# Stop old server
Write-Host "[4/7] Stopping old server..." -ForegroundColor Yellow
try {
    $StopScript = {
        taskkill /F /IM python.exe 2>$null
    }
    Invoke-Command -ComputerName $RemotePC -ScriptBlock $StopScript -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    Write-Host "  OK: Server stopped" -ForegroundColor Green
} catch {
    Write-Host "  WARNING: $_" -ForegroundColor Yellow
}

# Start new server
Write-Host "[5/7] Starting server..." -ForegroundColor Yellow
try {
    $StartScript = {
        param($Path)
        cd $Path
        Start-Process python -ArgumentList "server.py" -WindowStyle Hidden
    }
    Invoke-Command -ComputerName $RemotePC -ScriptBlock $StartScript -ArgumentList $RemotePath -ErrorAction Stop
    Write-Host "  OK: Server started" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: $_" -ForegroundColor Red
}

# Wait for server to initialize
Write-Host "[6/7] Waiting for server..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Check health endpoint
Write-Host "[7/7] Checking server health..." -ForegroundColor Yellow
try {
    $Response = Invoke-RestMethod -Uri "http://${RemotePC}:8000/health" -TimeoutSec 10
    Write-Host "  Status: $($Response.status)" -ForegroundColor Cyan
    Write-Host "  Loaded: $($Response.transcriber_loaded)" -ForegroundColor $(if ($Response.transcriber_loaded) { "Green" } else { "Yellow" })

    if ($Response.transcriber_loaded) {
        Write-Host ""
        Write-Host "========================================"  -ForegroundColor Green
        Write-Host "SUCCESS! Sherpa is working!"  -ForegroundColor Green
        Write-Host "========================================"  -ForegroundColor Green
        Write-Host ""
        Write-Host "Test on laptop: Press F9 → speak → F9" -ForegroundColor Cyan
        Write-Host "You should see 🌐 (globe) indicator!" -ForegroundColor Cyan
    } else {
        Write-Host ""
        Write-Host "========================================"  -ForegroundColor Yellow
        Write-Host "WARNING: transcriber_loaded=false"  -ForegroundColor Yellow
        Write-Host "========================================"  -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Sherpa installed but model not loaded." -ForegroundColor Yellow
        Write-Host "Try using Whisper instead (see MANUAL_SHERPA_INSTALL.md)" -ForegroundColor Cyan
    }
} catch {
    Write-Host "  ERROR: Cannot reach server - $_" -ForegroundColor Red
    Write-Host "  Check if server.py is running on remote PC" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Done!" -ForegroundColor Cyan
