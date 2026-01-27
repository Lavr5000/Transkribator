# Финальная инструкция по запуску Remote Transcriber

## ✅ Что уже сделано

### На удаленном ПК (REDACTED-LAN):
- ✅ Проект Transkribator скопирован на рабочий стол
- ✅ Структура папок создана:
  ```
  C:\Users\User1\Desktop\Transcriber\
  ├── src/                      # Исходный код транскрибатора
  ├── main.py                   # Главный файл
  ├── TranscriberServer/        # Серверная часть
  │   ├── server.py            # FastAPI сервер
  │   ├── transcriber_wrapper.py # Обёртка
  │   ├── requirements.txt     # Зависимости
  │   ├── results/             # Результаты (создастся автоматически)
  │   └── uploads/             # Загрузки (создастся автоматически)
  └── pyproject.toml
  ```
- ✅ Зависимости установлены
- ✅ AUTOSTART_SERVEO.bat обновлён (запускает сервер + туннель)

### На ноутбуке:
- ✅ CLI клиент создан: `C:\Users\user\.claude\REDACTED-PATH\Transkribator\TranscriberClient\`
- ✅ Документация готова

## 🚀 Финальные шаги для запуска

### Шаг 1: Перезапустить сеанс на удаленном ПК

**Важно:** Нужно выйти и зайти заново в Windows на удаленном ПК.

1. Подключитесь к удаленному ПК через RDP или зайдите физически
2. Выйдите из системы (Log off)
3. Зайдите снова

**Или** просто запустите файл `AUTOSTART_SERVEO.bat` на рабочем столе

### Шаг 2: Проверить что сервер запущен

На удаленном ПК откройте PowerShell и выполните:

```powershell
netstat -ano | findstr :8000
```

Должно показать что порт 8000 слушается (LISTENING).

### Шаг 3: Проверить логи

На рабочем столе откройте файл `serveo-tunnel.log` и проверьте:

```
[дата] Starting Transcriber Server...
[дата] Transcriber Server started on port 8000
[дата] Starting Serveo Tunnel...
[дата] Connecting to serveo.net...
```

### Шаг 4: Установить клиент на ноутбуке

```bash
cd "C:\Users\user\.claude\REDACTED-PATH\Transkribator\TranscriberClient"
pip install -r requirements.txt
```

### Шаг 5: Протестировать

```bash
cd "C:\Users\user\.claude\REDACTED-PATH\Transkribator\TranscriberClient"

# Проверить состояние сервера
python client.py --health

# Транскрибировать файл
python client.py path/to/audio.mp3
```

## 🔧 Если что-то не работает

### Проблема: "Connection refused"

**Причина:** SSH туннель не работает

**Решение:**
1. На удаленном ПК запустите `AUTOSTART_SERVEO.bat`
2. Подождите 10-15 секунд
3. Проверьте лог `serveo-tunnel.log`

### Проблема: "Health check failed"

**Причина:** Сервер транскрибатора не запущен

**Решение:**
1. На удаленном ПК проверьте процессы: `tasklist | findstr python`
2. Если нет процесса python - запустите вручную:
   ```batch
   cd C:\Users\User1\Desktop\Transcriber\TranscriberServer
   python -m uvicorn server:app --host 127.0.0.1 --port 8000
   ```

### Проблема: "Module not found"

**Причина:** Зависимости не установлены

**Решение:**
На удаленном ПК:
```batch
cd C:\Users\User1\Desktop\Transcriber\TranscriberServer
python -m pip install fastapi uvicorn python-multipart requests tqdm faster-whisper numpy soundfile
```

## 📊 Как это работает

```
[Ноутбук]                       [Удаленный ПК REDACTED-LAN]
    |                                  |
    |--[HTTP через Serveo]----------->|[FastAPI :8000]
    |                                  |  |
    |<--[Результат текст]--------------|--[WhisperTyping]
                                            (транскрибация)
```

**URL сервера:** `http://REDACTED-TUNNEL.serveo.net:8000`

## 📝 Ежедневное использование

### Быстрый старт (с ноутбука)

```bash
cd "C:\Users\user\.claude\REDACTED-PATH\Transkribator\TranscriberClient"
python client.py audio.mp3
```

### Результат

Файл сохранится в: `downloads/audio.txt`

## 🎯 Структура проекта

```
Transcriber/ (на рабочем столе удаленного ПК)
├── src/                    - код транскрибатора
├── TranscriberServer/      - FastAPI сервер
│   ├── server.py          - эндпоинты API
│   ├── transcriber_wrapper.py - обёртка над WhisperTyping
│   ├── results/           - результаты транскрибации
│   └── uploads/           - временные файлы
├── AUTOSTART_SERVEO.bat   - автозапуск (обновлён)
└── main.py                - точка входа WhisperTyping
```

## ✅ Проверочный лист перед использованием

На удаленном ПК:
- [ ] Зашли в систему (триггер автозапуска)
- [ ] Порт 8000 слушается (`netstat -ano | findstr :8000`)
- [ ] Логи чистые (`serveo-tunnel.log`)
- [ ] Модель Whisper загружена (первый запуск может занять 1-2 минуты)

На ноутбуке:
- [ ] `pip install -r requirements.txt` выполнен
- [ ] `python client.py --health` показывает "healthy"
- [ ] Тестовый файл транскрибирован успешно

## 📞 Следующие шаги

После успешного теста:

1. **Создать батник для быстрого запуска** на ноутбуке:
   ```batch
   @echo off
   cd "C:\Users\user\.claude\REDACTED-PATH\Transkribator\TranscriberClient"
   python client.py %1
   pause
   ```
   Сохранить как `transcribe.bat` и можно использовать:
   ```
   transcribe.bat audio.mp3
   ```

2. **Добавить в PATH** (опционально) для запуска из любой папки

3. **Настроить автоматическую очистку** старых результатов на сервере (опционально)

## 🎉 Готово!

Теперь вы можете транскрибировать аудиофайлы используя мощности удаленного ПК!
