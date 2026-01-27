@echo off
REM ==============================================================================
REM Serveo.net Autostart Script + Transcriber Server
REM ==============================================================================
REM Для работы на удаленном ПК (User1)
REM Путь проекта: C:\Users\User1\Desktop\Transcriber\
REM ==============================================================================

title Serveo Tunnel + Transcriber Server

REM Определяем путь к скрипту (относительная работа)
set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..

REM Лог-файл на рабочем столе
set LOGFILE=%USERPROFILE%\Desktop\transcriber-server.log

echo [%DATE% %TIME%] ======================================== >> %LOGFILE%
echo [%DATE% %TIME%] Starting Transcriber Server... >> %LOGFILE%
echo [%DATE% %TIME%] Script dir: %SCRIPT_DIR% >> %LOGFILE%
echo [%DATE% %TIME%] Project root: %PROJECT_ROOT% >> %LOGFILE%

REM 1. Запустить FastAPI сервер транскрибатора (в фоне)
REM ВАЖНО: Используем 0.0.0.0 для доступа через Tailscale
cd /d "%SCRIPT_DIR%"

REM Проверяем наличие Python
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [%DATE% %TIME%] ERROR: Python not found in PATH >> %LOGFILE%
    echo [%DATE% %TIME%] Trying portable Python... >> %LOGFILE%
    if exist "%PROJECT_ROOT%\python\python.exe" (
        set PATH=%PROJECT_ROOT%\python;%PATH%
    ) else (
        echo [%DATE% %TIME%] ERROR: No Python found! >> %LOGFILE%
        timeout /t 30
        exit /b 1
    )
)

echo [%DATE% %TIME%] Starting server with: python -m uvicorn server:app --host 0.0.0.0 --port 8000 >> %LOGFILE%
start /B python -m uvicorn server:app --host 0.0.0.0 --port 8000 >> %LOGFILE% 2>&1

echo [%DATE% %TIME%] Transcriber Server started on port 8000 >> %LOGFILE%
echo [%DATE% %TIME%] Starting Serveo Tunnel... >> %LOGFILE%

REM 2. Проверка и запуск туннеля serveo
:LOOP
echo [%DATE% %TIME%] Connecting to serveo.net... >> %LOGFILE%

ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=60 -o ServerAliveCountMax=3 -R elated-dhawan-remote:22:localhost:22 -R 8000:localhost:8000 serveo.net

REM Если туннель упал, ждем 10 секунд и перезапускаем
echo [%DATE% %TIME%] Connection lost. Reconnecting in 10 seconds... >> %LOGFILE%
timeout /t 10 /nobreak >nul

goto LOOP
