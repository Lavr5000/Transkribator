@echo off
REM Auto-start script for Transcriber Server - BACKGROUND MODE
REM Runs completely hidden (no console window)
REM Located on remote PC (192.168.31.9)

cd /d "%~dp0"

REM Check if already running
tasklist /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq TranscriberServer*" 2>NUL | find /I /N "python.exe">NUL
if "%ERRORLEVEL%"=="0" (
    REM Server already running
    exit /b 0
)

REM Активируем виртуальное окружение (если есть)
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Запускаем сервер в фоне (скрытое окно)
start /B python server.py > server_output.log 2>&1

REM Log startup
echo [%DATE% %TIME%] Transcriber Server started in background >> server_startup.log

exit /b 0
