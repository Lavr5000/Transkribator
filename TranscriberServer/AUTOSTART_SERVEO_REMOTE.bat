@echo off
REM ==============================================================================
REM Serveo.net Autostart Script + Transcriber Server
REM ==============================================================================
REM Запускается автоматически при входе в Windows
REM Создает SSH туннель для удаленного управления
REM Запускает FastAPI сервер транскрибатора на порту 8000
REM ==============================================================================

title Serveo Tunnel + Transcriber Server

set LOGFILE=C:\Users\User1\Desktop\serveo-tunnel.log

echo [%DATE% %TIME%] ======================================== >> %LOGFILE%
echo [%DATE% %TIME%] Starting Transcriber Server... >> %LOGFILE%

REM 1. Запустить FastAPI сервер транскрибатора (в фоне)
REM ВАЖНО: Используем 0.0.0.0 для доступа через Tailscale (не 127.0.0.1!)
cd C:\Users\User1\Desktop\Transcriber\TranscriberServer
start /B python -m uvicorn server:app --host 0.0.0.0 --port 8000 >> %LOGFILE% 2>&1

echo [%DATE% %TIME%] Transcriber Server started on port 8000 >> %LOGFILE%
echo [%DATE% %TIME%] Starting Serveo Tunnel... >> %LOGFILE%

REM 2. Проверка и запуск туннеля
:LOOP
echo [%DATE% %TIME%] Connecting to serveo.net... >> %LOGFILE%

ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=60 -o ServerAliveCountMax=3 -R elated-dhawan-remote:22:localhost:22 -R 8000:localhost:8000 serveo.net

REM Если туннель упал, ждем 10 секунд и перезапускаем
echo [%DATE% %TIME%] Connection lost. Reconnecting in 10 seconds... >> %LOGFILE%
timeout /t 10 /nobreak >nul

goto LOOP
