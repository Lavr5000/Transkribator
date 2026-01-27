@echo off
REM Complete autostart: Transcriber Server + Serveo.net tunnel
REM This script starts both server and SSH tunnel

cd /d "%~dp0"

echo ========================================
echo Transcriber Server - Full Autostart
echo ========================================
echo.

REM Активируем виртуальное окружение (если есть)
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo Virtual environment activated
)

echo.
echo [1/2] Starting Transcriber Server on port 8000...
start /B python server.py

REM Wait for server to initialize
timeout /t 3 /nobreak > nul

echo [2/2] Starting Serveo.net tunnel...
echo.

REM Start Serveo.net tunnel с автоматическим перезапуском
:LOOP
    ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=60 -o ServerAliveCountMax=3 -R elated-dhawan-remote:22:localhost:22 serveo.net

    echo [%DATE% %TIME%] SSH connection lost. Reconnecting in 10 seconds...
    timeout /t 10 /nobreak > nul
    goto LOOP
