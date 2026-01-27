# Инструкция по исправлению удаленного сервера транскрибатора

## Проблема
Сервер транскрибатора на удаленном ПК недоступен через Tailscale, потому что запущен на `127.0.0.1` вместо `0.0.0.0`.

## Решение
Обновить файл `AUTOSTART_SERVEO_UPDATED.bat` на удаленном ПК.

---

## Варианты применения исправления

### Вариант 1: Через RDP (Рекомендуемый)

1. **Подключиться к удаленному ПК через RDP**
   - IP: 192.168.31.9 (если в одной сети)
   - Или через Tailscale IP: 100.102.178.110
   - Пользователь: User1

2. **Заменить файл на удаленном ПК**
   ```
   Удаленный ПК: C:\Users\user\.claude\0 ProEKTi\Transkribator\TranscriberServer\AUTOSTART_SERVEO_UPDATED.bat
   ```

   Заменить содержимое строки 19:
   ```batch
   # Было:
   start /B python -m uvicorn server:app --host 127.0.0.1 --port 8000

   # Стало:
   start /B python -m uvicorn server:app --host 0.0.0.0 --port 8000
   ```

3. **Перезапустить сервер**
   - Открыть Task Manager (Диспетчер задач)
   - Найти все процессы `python.exe` и завершить их
   - Запустить файл `AUTOSTART_SERVEO_UPDATED.bat` двойным кликом

4. **Проверить работу**
   - С ноутбука выполнить: `curl http://100.102.178.110:8000/health`
   - Должно вернуться: `{"status": "healthy", ...}`

---

### Вариант 2: Скопировать через сетевую папку (если настроена)

Если есть доступ к сетевой папке на удаленном ПК:

```powershell
# С ноутбука
Copy-Item "C:\Users\user\.claude\0 ProEKTi\Transkribator\RemotePackage\TranscriberServer\AUTOSTART_SERVEO_UPDATED.bat" `
    -Destination "\\100.102.178.110\c$\Users\user\.claude\0 ProEKTi\Transkribator\TranscriberServer\AUTOSTART_SERVEO_UPDATED.bat" `
    -Force
```

Затем перезапустить сервер через PowerShell Remoting или RDP.

---

### Вариант 3: Через PowerShell Remoting (если WinRM настроен)

```powershell
# 1. Подключиться к удаленному ПК
$session = New-PSSession -ComputerName 100.102.178.110 -Credential User1

# 2. Остановить старый процесс
Invoke-Command -Session $session -ScriptBlock {
    Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
}

# 3. Скопировать исправленный файл
Copy-Item "C:\Users\user\.claude\0 ProEKTi\Transkribator\RemotePackage\TranscriberServer\AUTOSTART_SERVEO_UPDATED.bat" `
    -Destination "C:\Users\user\.claude\0 ProEKTi\Transkribator\TranscriberServer\" `
    -ToSession $session `
    -Force

# 4. Запустить новый сервер
Invoke-Command -Session $session -ScriptBlock {
    Start-Process -FilePath "C:\Users\user\.claude\0 ProEKTi\Transkribator\TranscriberServer\AUTOSTART_SERVEO_UPDATED.bat" `
        -WorkingDirectory "C:\Users\user\.claude\0 ProEKTi\Transkribator\TranscriberServer"
}

Remove-PSSession $session
```

---

## Проверка результата

После применения исправления:

```bash
# 1. Проверить health endpoint
curl http://100.102.178.110:8000/health

# 2. Проверить порт
netstat -an | findstr 8000

# 3. Запустить транскрибатор и проверить логи
# Должно появиться сообщение: "Server healthy: http://100.102.178.110:8000"
```

---

## Если не работает

1. **Проверить логи на удаленном ПК:**
   ```
   C:\Users\User1\Desktop\serveo-tunnel.log
   ```

2. **Убедиться, что Tailscale запущен на удаленном ПК**

3. **Проверить firewall:**
   ```
   # На удаленном ПК
   New-NetFirewallRule -DisplayName "Transcriber Server" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
   ```

---

## Исправленный файл (готов к копированию)

```batch
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
cd C:\Users\user\.claude\0 ProEKTi\Transkribator\TranscriberServer
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
```

---

**Дата создания:** 2026-01-26
**Статус:** Ожидает применения на удаленном ПК
