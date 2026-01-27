# Установка автозапуска Transcriber Server

## На удаленном ПК (192.168.31.9)

### 1. Скопировать файлы
Убедитесь что на удаленном ПК есть:
- `TranscriberServer/server.py`
- `TranscriberServer/transcriber_wrapper.py`
- `TranscriberServer/START_SERVER.bat`
- `TranscriberServer/install_scheduled_task.ps1`
- `TranscriberServer/AUTOSTART_TRANSCRIBER_FULL.bat`

### 2. Установить Scheduled Task
Откройте PowerShell от имени Администратора:
```powershell
cd C:\path\to\TranscriberServer
powershell -ExecutionPolicy Bypass -File install_scheduled_task.ps1
```

### 3. Проверить установку
Откройте Task Scheduler:
- Win+R → `taskschd.msc`
- Найдите задачу "TranscriberServer"
- Проверьте что она настроена на "At Logon"

### 4. Тестировать ручной запуск
```batch
cd C:\path\to\TranscriberServer
START_SERVER.bat
```

Сервер должен запуститься на http://192.168.31.9:8000

### 5. Проверить через ноутбук
На ноутбуке:
```bash
curl http://192.168.31.9:8000/health
```

Должен вернуть:
```json
{"status": "healthy", "transcriber_loaded": true}
```

### 6. Перезалогиниться
Перезайдите в систему на удаленном ПК для проверки автозапуска.

## Готово!

Теперь при каждом логоне на удаленном ПК будет автоматически запускаться сервер.
