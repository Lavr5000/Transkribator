@echo off
echo ========================================
echo Setting up Transcriber Server Autostart
echo ========================================
echo.

cd /d "%~dp0"

powershell -ExecutionPolicy Bypass -Command ^
  "$RemotePC = '192.168.31.119';" ^
  "$ServerPath = 'C:\Users\user\.claude\0 ProEKTi\Transkribator\TranscriberServer';" ^
  "$TaskName = 'TranscriberServer-Autostart';" ^
  "Write-Host '[1/3] Testing WinRM...' -ForegroundColor Yellow;" ^
  "Invoke-Command -ComputerName $RemotePC -ScriptBlock { 'WinRM OK' } | Out-Null;" ^
  "Write-Host 'OK WinRM works' -ForegroundColor Green;" ^
  "Write-Host '[2/3] Creating start script...' -ForegroundColor Yellow;" ^
  "$bat = '@echo off cd /d ' + $ServerPath + ' start /B python server.py';" ^
  "$bat | Out-File '$env:TEMP\start_server_autostart.bat' -Encoding ASCII;" ^
  "Copy-Item '$env:TEMP\start_server_autostart.bat' ('\\' + $RemotePC + '\C$\Users\user\.claude\0 ProEKTi\Transkribator\TranscriberServer\start_server_autostart.bat') -Force;" ^
  "Write-Host 'OK Script copied' -ForegroundColor Green;" ^
  "Write-Host '[3/3] Creating Scheduled Task...' -ForegroundColor Yellow;" ^
  "Unregister-ScheduledTask -TaskName $TaskName -TaskPath '\Transcriber' -ComputerName $RemotePC -ErrorAction SilentlyContinue;" ^
  "$Action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument ('/C \"' + $ServerPath + '\start_server_autostart.bat\"') -WorkingDirectory $ServerPath;" ^
  "$Trigger = New-ScheduledTaskTrigger -AtStartup;" ^
  "$Principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest;" ^
  "$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable;" ^
  "Register-ScheduledTask -TaskName $TaskName -TaskPath '\Transcriber' -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -ComputerName $RemotePC -Force;" ^
  "Write-Host 'OK Task created' -ForegroundColor Green;" ^
  "Start-ScheduledTask -TaskName $TaskName -TaskPath '\Transcriber' -ComputerName $RemotePC;" ^
  "Write-Host 'Waiting 10 sec...' -ForegroundColor Cyan;" ^
  "Start-Sleep -Seconds 10;" ^
  "try { $h = Invoke-RestMethod -Uri ('http://' + $RemotePC + ':8000/health') -TimeoutSec 10; Write-Host ('OK Server running! ' + $h.status) -ForegroundColor Green } catch { Write-Host 'Server starting...' -ForegroundColor Yellow };"

echo.
echo ========================================
echo DONE! Server will auto-start on boot.
echo ========================================
echo.
echo Test with: curl http://192.168.31.119:8000/health
echo.
pause
