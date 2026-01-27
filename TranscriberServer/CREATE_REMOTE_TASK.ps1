# Create Scheduled Task on remote PC to run installation

$RemotePC = "192.168.31.119"
$TaskName = "InstallSherpa"

Write-Host "Creating Scheduled Task on remote PC..." -ForegroundColor Cyan

# Create batch script content
$BatchScript = @"
@echo off
cd /d C:\Users\Denis\TranscriberServer
echo [%DATE% %TIME%] Starting Sherpa installation >> install_log.txt

echo [1/4] Installing sherpa-onnx... >> install_log.txt
pip install sherpa-onnx >> install_log.txt 2>&1

echo [2/4] Checking src folder... >> install_log.txt
if exist src (
    echo   src folder exists >> install_log.txt
) else (
    echo   ERROR: src folder missing >> install_log.txt
)

echo [3/4] Restarting server... >> install_log.txt
taskkill /F /IM python.exe >> install_log.txt 2>&1
timeout /t 2 /nobreak > nul
start /B python server.py >> install_log.txt 2>&1

echo [4/4] Waiting and checking... >> install_log.txt
timeout /t 5 /nobreak > nul
curl -s http://192.168.31.9:8000/health >> install_log.txt 2>&1

echo Done! >> install_log.txt
"@

# Save to temp file
$TempFile = "$env:TEMP\install_sherpa.bat"
$BatchScript | Out-File -FilePath $TempFile -Force -Encoding ASCII

# Copy to remote PC
$RemotePath = "\\$RemotePC\C$\Users\user\.claude\0 ProEKTi\Transkribator\TranscriberServer\install_sherpa.bat"
Copy-Item -Path $TempFile -Destination $RemotePath -Force -ErrorAction SilentlyContinue

# Create scheduled task action
$Action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/C C:\Users\user\.claude\0 ProEKTi\Transkribator\TranscriberServer\install_sherpa.bat" -WorkingDirectory "C:\Users\user\.claude\0 ProEKTi\Transkribator\TranscriberServer"

# Create trigger (run immediately)
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date)

# Principal (SYSTEM user)
$Principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

# Register task
try {
    Register-ScheduledTask -TaskName $TaskName -TaskPath "\Transcriber" -Action $Action -Trigger $Trigger -Principal $Principal -ComputerName $RemotePC -Force -ErrorAction Stop
    Write-Host "  Task created successfully" -ForegroundColor Green

    # Start task
    Start-ScheduledTask -TaskName "$TaskName" -TaskPath "\Transcriber" -ComputerName $RemotePC
    Write-Host "  Task started" -ForegroundColor Green

    # Wait for completion
    Write-Host "  Waiting for task to complete..." -ForegroundColor Yellow
    Start-Sleep -Seconds 30

    # Check log
    Write-Host ""
    Write-Host "Remote installation log:" -ForegroundColor Cyan
    $Log = Invoke-Command -ComputerName $RemotePC -ScriptBlock { Get-Content "C:\Users\user\.claude\0 ProEKTi\Transkribator\TranscriberServer\install_log.txt" } -ErrorAction SilentlyContinue
    if ($Log) {
        $Log | Write-Output
    }

    # Check health
    Write-Host ""
    Write-Host "Server health:" -ForegroundColor Cyan
    $Health = Invoke-RestMethod -Uri "http://${RemotePC}:8000/health" -TimeoutSec 10 -ErrorAction SilentlyContinue
    if ($Health) {
        Write-Host "  Status: $($Health.status)"
        Write-Host "  Loaded: $($Health.transcriber_loaded)"

        if (-not $Health.transcriber_loaded) {
            Write-Host ""
            Write-Host "Model not loaded. Trying Whisper backend..." -ForegroundColor Yellow

            # Create Whisper switch script
            $WhisperScript = @"
@echo off
cd C:\Users\user\.claude\0 ProEKTi\Transkribator\TranscriberServer
echo Switching to Whisper...
powershell -Command "(gc transcriber_wrapper.py) -replace 'backend=\"sherpa\"', 'backend=\"whisper\"' -replace 'model_size=\"giga-am-v2-ru\"', 'model_size=\"base\"' | Set-Content transcriber_wrapper.py"
taskkill /F /IM python.exe
timeout /t 2 /nobreak > nul
start /B python server.py
timeout /t 5 /nobreak > nul
curl -s http://192.168.31.119:8000/health
"@
            $WhisperScript | Out-File -FilePath "$env:TEMP\switch_whisper.bat" -Force -Encoding ASCII
            Copy-Item -Path "$env:TEMP\switch_whisper.bat" -Destination "\\$RemotePC\C$\Users\user\.claude\0 ProEKTi\Transkribator\TranscriberServer\switch_whisper.bat" -Force

            $Action2 = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/C C:\Users\user\.claude\0 ProEKTi\Transkribator\TranscriberServer\switch_whisper.bat" -WorkingDirectory "C:\Users\user\.claude\0 ProEKTi\Transkribator\TranscriberServer"
            $Trigger2 = New-ScheduledTaskTrigger -Once -At (Get-Date)
            Register-ScheduledTask -TaskName "SwitchToWhisper" -TaskPath "\Transcriber" -Action $Action2 -Trigger $Trigger2 -Principal $Principal -ComputerName $RemotePC -Force
            Start-ScheduledTask -TaskName "SwitchToWhisper" -TaskPath "\Transcriber" -ComputerName $RemotePC
            Start-Sleep -Seconds 15

            $Health2 = Invoke-RestMethod -Uri "http://${RemotePC}:8000/health" -TimeoutSec 10 -ErrorAction SilentlyContinue
            if ($Health2) {
                Write-Host "  After Whisper switch - Loaded: $($Health2.transcriber_loaded)"
            }
        }
    }

} catch {
    Write-Host "ERROR: $_" -ForegroundColor Red
}

# Cleanup temp files
Remove-Item -Path $TempFile -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Done!" -ForegroundColor Cyan
