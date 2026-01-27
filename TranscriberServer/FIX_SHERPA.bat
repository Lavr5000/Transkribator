@echo off
REM Fix Sherpa installation on remote server
REM This will install sherpa-onnx and required dependencies

set REMOTE_HOST=192.168.31.9
set REMOTE_USER=Denis
set REMOTE_PATH=C:\Users\Denis\TranscriberServer

echo ========================================
echo Fixing Sherpa on Remote Server
echo ========================================
echo.

echo [1/5] Installing sherpa-onnx...
ssh -o StrictHostKeyChecking=no %REMOTE_USER%@%REMOTE_HOST% "pip install sherpa-onnx"
echo.

echo [2/5] Checking installation...
ssh -o StrictHostKeyChecking=no %REMOTE_USER%@%REMOTE_HOST% "python -c \"import sherpa_onnx; print('sherpa-onnx version:', sherpa_onnx.__version__)\""
echo.

echo [3/5] Stopping old server...
ssh -o StrictHostKeyChecking=no %REMOTE_USER%@%REMOTE_HOST% "taskkill /F /IM python.exe 2>nul"
echo.

echo [4/5] Copying fixed transcriber_wrapper.py...
scp -o StrictHostKeyChecking=no transcriber_wrapper.py %REMOTE_USER%@%REMOTE_HOST%:%REMOTE_PATH%\
echo.

echo [5/5] Starting server...
ssh -o StrictHostKeyChecking=no %REMOTE_USER%@%REMOTE_HOST% "cd %REMOTE_PATH% && start /B python server.py"
echo.

echo Waiting for server to start...
timeout /t 5 /nobreak > nul

echo Verifying...
powershell -Command "try { $response = Invoke-RestMethod -Uri 'http://%REMOTE_HOST%:8000/health' -TimeoutSec 5 ; Write-Host \"Status: $($response.status)\" ; Write-Host \"Loaded: $($response.transcriber_loaded)\" } catch { Write-Host \"Error: $_\" }"
echo.

echo ========================================
echo Complete!
echo ========================================
echo.
echo If Loaded: False above, manual intervention may be needed.
echo Try running diagnose_server.py on remote PC.
echo.
pause
