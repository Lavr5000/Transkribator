@echo off
REM Auto-start script for Transcriber Server
REM Located on remote PC (192.168.31.9)

cd /d "%~dp0"

echo ========================================
echo Transcriber Server - Auto Start
echo ========================================
echo.

REM Активируем виртуальное окружение (если есть)
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo Virtual environment activated
)

REM Запускаем сервер
echo Starting Transcriber Server on port 8000...
python server.py

REM Если сервер упал - пауза перед выходом
echo.
echo Server stopped. Press any key to exit...
pause
