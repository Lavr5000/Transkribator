@echo off
echo ========================================
echo Complete Autostart Setup for Transcriber
echo ========================================
echo.
echo This script will:
echo 1. Create Scheduled Task on remote PC (192.168.31.119)
echo 2. Start server immediately for testing
echo 3. Verify server is running
echo.
echo Press any key to continue...
pause > nul

echo.
echo [Step 1] Adding remote PC to TrustedHosts...
powershell -NoProfile -Command "Set-Item WSMan:\localhost\Client\TrustedHosts -Value '192.168.31.119' -Force"
echo OK TrustedHosts updated
echo.

echo [Step 2] Creating start script on remote PC...
powershell -NoProfile -Command "Invoke-Command -ComputerName 192.168.31.119 -ScriptBlock {
    \$bat = '@echo off
cd /d C:\Users\user\.claude\0 ProEKTi\Transkribator\TranscriberServer
echo %%DATE%% %%TIME%% Starting Transcriber Server ^>^> server_startup.log
start /B python server.py ^>^> server_output.log 2^>^&1'
    \$bat | Out-File 'C:\Users\user\.claude\0 ProEKTi\Transkribator\TranscriberServer\start_server_autostart.bat' -Encoding ASCII
}"
echo OK Start script created
echo.

echo [Step 3] Creating Scheduled Task...
powershell -NoProfile -Command "Invoke-Command -ComputerName 192.168.31.119 -ScriptBlock {
    Unregister-ScheduledTask -TaskName 'TranscriberServer-Autostart' -TaskPath '\Transcriber' -ErrorAction SilentlyContinue
    \$path = 'C:\Users\user\.claude\0 ProEKTi\Transkribator\TranscriberServer'
    \$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument '/C start_server_autostart.bat' -WorkingDirectory \$path
    \$trigger = New-ScheduledTaskTrigger -AtStartup
    \$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
    \$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
    Register-ScheduledTask -TaskName 'TranscriberServer-Autostart' -TaskPath '\Transcriber' -Action \$action -Trigger \$trigger -Principal \$principal -Settings \$settings -Force | Out-Null
}"
echo OK Scheduled Task created
echo.

echo [Step 4] Starting server immediately...
powershell -NoProfile -Command "Invoke-Command -ComputerName 192.168.31.119 -ScriptBlock {
    cd 'C:\Users\user\.claude\0 ProEKTi\Transkribator\TranscriberServer'
    start /B python server.py
}"
echo OK Server started
echo.

echo [Step 5] Waiting for server to initialize (30 seconds)...
timeout /t 30 /nobreak > nul
echo.

echo [Step 6] Checking server health...
curl -s http://192.168.31.119:8000/health
echo.
echo.

echo ========================================
echo SETUP COMPLETE!
echo ========================================
echo.
echo The Scheduled Task has been created and will automatically start
echo the Transcriber Server when the remote PC boots up.
echo.
echo To verify:
echo   curl http://192.168.31.119:8000/health
echo.
echo Expected response:
echo   {"status":"healthy","transcriber_loaded":true}
echo.
echo If server is not responding yet, wait 1-2 minutes for model to load.
echo.
pause
