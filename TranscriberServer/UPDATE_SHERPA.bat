@echo off
REM Update Sherpa backend on remote server (192.168.31.9)
REM This script copies files via SCP and runs diagnostics

set REMOTE_HOST=192.168.31.9
set REMOTE_USER=Denis
set REMOTE_PATH=C:\Users\Denis\TranscriberServer

echo ========================================
echo Updating Sherpa Backend on Remote Server
echo ========================================
echo.

echo [1/6] Checking SSH connection...
ping -n 1 %REMOTE_HOST% > nul
if errorlevel 1 (
    echo ERROR: Cannot reach %REMOTE_HOST%
    pause
    exit /b 1
)
echo OK: Server is reachable
echo.

echo [2/6] Copying diagnostic script...
scp -o StrictHostKeyChecking=no diagnose_server.py %REMOTE_USER%@%REMOTE_HOST%:%REMOTE_PATH%\
if errorlevel 1 (
    echo ERROR: Failed to copy diagnostic script
    pause
    exit /b 1
)
echo OK: Diagnostic script copied
echo.

echo [3/6] Running diagnostics on remote server...
ssh -o StrictHostKeyChecking=no %REMOTE_USER%@%REMOTE_HOST% "cd %REMOTE_PATH% && python diagnose_server.py"
echo.

echo [4/6] Installing sherpa-onnx if needed...
ssh -o StrictHostKeyChecking=no %REMOTE_USER%@%REMOTE_HOST% "pip install sherpa-onnx"
echo.

echo [5/6] Restarting server...
ssh -o StrictHostKeyChecking=no %REMOTE_USER%@%REMOTE_HOST% "taskkill /F /IM python.exe 2>nul ; timeout /t 2 /nobreak > nul ; cd %REMOTE_PATH% && start /B python server.py"
echo.

echo [6/6] Verifying server health...
timeout /t 3 /nobreak > nul
powershell -Command "try { $response = Invoke-RestMethod -Uri 'http://%REMOTE_HOST%:8000/health' -TimeoutSec 5 ; Write-Host \"Status: $($response.status)\" ; Write-Host \"Loaded: $($response.transcriber_loaded)\" } catch { Write-Host \"Error: $_\" }"
echo.

echo ========================================
echo Update Complete!
echo ========================================
echo.
echo Check the diagnostics above. If "Loaded: False",
echo then sherpa-onnx might need manual installation.
echo.
pause
