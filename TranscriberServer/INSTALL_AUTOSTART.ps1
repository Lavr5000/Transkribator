# Script to setup autostart on remote PC
 = "192.168.31.119"
 = "C:\Users\user\.claude\0 ProEKTi\Transkribator\TranscriberServer"
 = "TranscriberServer-Autostart"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Setting up server autostart on " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Test WinRM connection
Write-Host "[1/6] Testing WinRM connection..." -ForegroundColor Yellow
try {
     = Invoke-Command -ComputerName  -ScriptBlock { "WinRM OK" } -ErrorAction Stop
    Write-Host "      OK WinRM connection works" -ForegroundColor Green
} catch {
    Write-Host "      ERROR WinRM: C:\Users\user\.claude\0 ProEKTi\Transkribator\TranscriberServer" -ForegroundColor Red
    Write-Host ""
    Write-Host "To enable WinRM on PC, run:" -ForegroundColor Yellow
    Write-Host "  Enable-PSRemoting -Force" -ForegroundColor Cyan
    Write-Host "  Set-Item WSMan:localhostClientTrustedHosts -Value '' -Force" -ForegroundColor Cyan
    exit 1
}

# Create start script
Write-Host "[2/6] Creating start script..." -ForegroundColor Yellow
 = "@
@echo off
cd /d 
echo [%DATE% %TIME%] Starting Transcriber Server >> server_startup.log
start /B python server.py >> server_output.log 2>&1
echo [%DATE% %TIME%] Server started >> server_startup.log
@"

 = ":TEMP\start_server_autostart.bat"
 | Out-File -FilePath  -Force -Encoding ASCII
 = "$RemotePC\C$\Users\user\.claude\0 ProEKTi\Transkribator\TranscriberServer\start_server_autostart.bat"

try {
    Copy-Item -Path  -Destination  -Force -ErrorAction Stop
    Write-Host "      OK Script copied to PC" -ForegroundColor Green
} catch {
    Write-Host "      ERROR Copy failed: C:\Users\user\.claude\0 ProEKTi\Transkribator\TranscriberServer" -ForegroundColor Red
    exit 1
}

# Remove old task
Write-Host "[3/6] Removing old Scheduled Task..." -ForegroundColor Yellow
try {
    Unregister-ScheduledTask -TaskName "" -TaskPath "\Transcriber" -ComputerName  -ErrorAction SilentlyContinue
    Write-Host "      OK Old task removed" -ForegroundColor Green
} catch {
    Write-Host "      INFO Old task not found" -ForegroundColor Cyan
}

# Create Scheduled Task
Write-Host "[4/6] Creating Scheduled Task..." -ForegroundColor Yellow
try {
     = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/C ""\start_server_autostart.bat""" -WorkingDirectory 
     = New-ScheduledTaskTrigger -AtStartup
     = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
     = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

    Register-ScheduledTask -TaskName  -TaskPath "\Transcriber" -Action  -Trigger  -Principal  -Settings  -ComputerName  -Force -ErrorAction Stop

    Write-Host "      OK Scheduled Task created: " -ForegroundColor Green
} catch {
    Write-Host "      ERROR: C:\Users\user\.claude\0 ProEKTi\Transkribator\TranscriberServer" -ForegroundColor Red
    exit 1
}

# Verify task
Write-Host "[5/6] Verifying task creation..." -ForegroundColor Yellow
 = Get-ScheduledTask -TaskName "" -TaskPath "\Transcriber" -ComputerName  -ErrorAction SilentlyContinue
if () {
    Write-Host "      OK Task created successfully" -ForegroundColor Green
} else {
    Write-Host "      ERROR Task not found\!" -ForegroundColor Red
    exit 1
}

# Start task immediately
Write-Host "[6/6] Starting server for test..." -ForegroundColor Yellow
try {
    Start-ScheduledTask -TaskName "" -TaskPath "\Transcriber" -ComputerName  -ErrorAction Stop
    Write-Host "      OK Task started" -ForegroundColor Green
} catch {
    Write-Host "      WARNING: C:\Users\user\.claude\0 ProEKTi\Transkribator\TranscriberServer" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Waiting for server to start (10 sec)..." -ForegroundColor Cyan
Start-Sleep -Seconds 10

Write-Host ""
Write-Host "Checking server health..." -ForegroundColor Cyan
try {
     = Invoke-RestMethod -Uri "http://:8000/health" -TimeoutSec 10 -ErrorAction Stop
    Write-Host "      OK Server is running\!" -ForegroundColor Green
    Write-Host "         Status: " -ForegroundColor Cyan
    Write-Host "         Model: " -ForegroundColor Cyan
} catch {
    Write-Host "      INFO Server not responding yet (normal on first run)" -ForegroundColor Yellow
    Write-Host "      Check manually: curl http://:8000/health" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "DONE\! Server will auto-start on Windows boot." -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Reboot PC to test autostart" -ForegroundColor White
Write-Host "  2. After reboot check: curl http://:8000/health" -ForegroundColor White
Write-Host "  3. Run Transkribator on laptop - should show globe icon" -ForegroundColor White