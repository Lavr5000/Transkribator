# Инструкция по установке Remote Transcriber

## 📋 Обзор

Эта инструкция поможет настроить систему удаленной транскрибации аудиофайлов с использованием мощностей удаленного ПК.

**Компоненты:**
- **Сервер** (удаленный ПК REDACTED-LAN): FastAPI + WhisperTyping
- **Клиент** (ноутбук): CLI для отправки файлов и получения результатов

## 🚀 Пошаговая установка

### Step 1: Установка на удаленном ПК

#### 1.1. Скопировать проект Transkribator

Уже должно быть: `C:\Users\user\.claude\REDACTED-PATH\Transkribator`

Если нет - скопируйте с ноутбука через SSH:

```bash
# На ноутбуке
scp -r ".claude/REDACTED-PATH/Transkribator" User1@REDACTED-TUNNEL:/Users/User1/.claude/REDACTED-PATH/
```

#### 1.2. Установить Python на удаленном ПК (если не установлен)

Проверьте версию:
```bash
python --version
```

Если не установлен - скачайте с python.org

#### 1.3. Установить зависимости сервера

На удаленном ПК (через SSH или RDP):

```bash
cd C:\Users\user\.claude\REDACTED-PATH\Transkribator\TranscriberServer
pip install -r requirements.txt
```

#### 1.4. Протестировать сервер

На удаленном ПК:

```bash
cd C:\Users\user\.claude\REDACTED-PATH\Transkribator\TranscriberServer
python -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload
```

Откройте в браузере: http://127.0.0.1:8000/docs

Должна открыться документация FastAPI.

#### 1.5. Обновить автозапуск

Замените содержимое `C:\Users\User1\Desktop\AUTOSTART_SERVEO.bat` на:

```batch
@echo off
title Serveo Tunnel + Transcriber Server

set LOGFILE=C:\Users\User1\Desktop\serveo-tunnel.log

echo [%DATE% %TIME%] Starting Transcriber Server... >> %LOGFILE%

REM 1. Запустить FastAPI сервер
cd C:\Users\user\.claude\REDACTED-PATH\Transkribator\TranscriberServer
start /B python -m uvicorn server:app --host 127.0.0.1 --port 8000 >> %LOGFILE% 2>&1

echo [%DATE% %TIME%] Transcriber Server started on port 8000 >> %LOGFILE%

REM 2. SSH туннель с пробросом порта 8000
:LOOP
ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=60 -o ServerAliveCountMax=3 -R REDACTED-TUNNEL:22:localhost:22 -R 8000:localhost:8000 serveo.net

echo [%DATE% %TIME%] Connection lost. Reconnecting in 10 seconds... >> %LOGFILE%
timeout /t 10 /nobreak >nul
goto LOOP
```

#### 1.6. Перезапустить сеанс на удаленном ПК

Выйти из Windows и зайти снова. Сервер должен запуститься автоматически.

Проверить логи:
```bash
type C:\Users\User1\Desktop\serveo-tunnel.log
```

### Step 2: Установка на ноутбуке

#### 2.1. Установить зависимости клиента

На ноутбуке:

```bash
cd "C:\Users\user\.claude\REDACTED-PATH\Transkribator\TranscriberClient"
pip install -r requirements.txt
```

#### 2.2. Проверить состояние сервера

```bash
cd "C:\Users\user\.claude\REDACTED-PATH\Transkribator\TranscriberClient"
python client.py --health
```

Ожидаемый результат:
```
Проверка состояния сервера...
✓ Сервер доступен
  Статус: healthy
  Транскрибатор: загружен
```

Если ошибка - проверьте что:
1. Удаленный ПК включен
2. SSH туннель работает
3. FastAPI сервер запущен

### Step 3: Тестирование

#### 3.1. Подготовить тестовый файл

Создайте или используйте любой `.mp3` файл.

#### 3.2. Запустить транскрибацию

```bash
cd "C:\Users\user\.claude\REDACTED-PATH\Transkribator\TranscriberClient"
python client.py test_audio.mp3
```

Ожидаемый результат:
```
==================================================
REMOTE TRANSCRIBER
==================================================

[1/3] Загрузка файла: test_audio.mp3
      Размер: X.XX MB
      ✓ Task ID: abc-123-def
      Файл: test_audio.mp3
[2/3] Транскрибация...
Прогресс: 10сек... 20сек...
      ✓ Готово! (за X.X сек)
[3/3] Получение результата...
      ✓ Сохранено: downloads\test_audio.txt

==================================================
РЕЗУЛЬТАТ ТРАНСКРИБАЦИИ
==================================================

<transcribed text here>

==================================================
```

## 🔧 Troubleshooting

### Сервер не запускается

**Проверка:**
```bash
# На удаленном ПК
netstat -ano | findstr :8000
```

Если пусто - сервер не запущен. Проверьте логи:
```bash
type C:\Users\User1\Desktop\serveo-tunnel.log
```

**Решение:**
Запустите вручную для отладки:
```bash
cd C:\Users\user\.claude\REDACTED-PATH\Transkribator\TranscriberServer
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

### Ошибка "Cannot connect to server"

**Причины:**
1. Удаленный ПК выключен
2. SSH туннель не работает
3. Порт 8000 не проброшен

**Проверка:**
```bash
# На ноутбуке
python client.py --health
```

**Решение:**
1. Включите удаленный ПК
2. Проверьте логи на удаленном ПК
3. Проверьте что в AUTOSTART_SERVEO.bat есть `-R 8000:localhost:8000`

### Ошибка "Module not found"

**На сервере:**
```bash
cd C:\Users\user\.claude\REDACTED-PATH\Transkribator\TranscriberServer
pip install -r requirements.txt
```

**На клиенте:**
```bash
cd "C:\Users\user\.claude\REDACTED-PATH\Transkribator\TranscriberClient"
pip install -r requirements.txt
```

### Транскрибация очень медленная

**Причина:** CPU bottleneck

**Решение:**
1. Используйте модель `tiny` вместо `base` (быстрее, но менее точно)
2. Используйте GPU если доступна NVIDIA видеокарта

Отредактируйте `transcriber_wrapper.py`:
```python
self.transcriber = Transcriber(
    model_size="tiny",  # вместо "base"
    device="cuda",      # если есть NVIDIA GPU
)
```

## 📊 Мониторинг

### Логи сервера

На удаленном ПК:
```bash
# Просмотр логов
type C:\Users\User1\Desktop\serveo-tunnel.log

# Или откройте файл в текстовом редакторе
notepad C:\Users\User1\Desktop\serveo-tunnel.log
```

### Статистика использования

Проверьте папку `results/` на удаленном ПК:
```bash
dir C:\Users\user\.claude\REDACTED-PATH\Transkribator\TranscriberServer\results
```

## 🎯 Ежедневное использование

### Запуск транскрибации

```bash
cd "C:\Users\user\.claude\REDACTED-PATH\Transkribator\TranscriberClient"
python client.py path/to/audio.mp3
```

### Автоматизация (опционально)

Создайте батник для быстрого запуска:

`transcribe.bat`:
```batch
@echo off
cd "C:\Users\user\.claude\REDACTED-PATH\Transkribator\TranscriberClient"
python client.py %1
pause
```

Использование:
```bash
transcribe.bat audio.mp3
```

Или добавьте в PATH для запуска из любой папки.

## ✅ Проверочный лист

Установлено на удаленном ПК:
- [ ] Python установлен
- [ ] Transkribator скопирован
- [ ] Зависимости сервера установлены
- [ ] Сервер запускается локально
- [ ] AUTOSTART_SERVEO.bat обновлён
- [ ] Сервер запускается при входе в Windows
- [ ] Порт 8000 проброшен через SSH

Установлено на ноутбуке:
- [ ] Зависимости клиента установлены
- [ ] `python client.py --health` работает
- [ ] Тестовая транскрибация успешна

## 📞 Поддержка

При проблемах проверьте:
1. Логи на удаленном ПК
2. Состояние сервера: `python client.py --health`
3. Документацию API: http://REDACTED-TUNNEL.serveo.net:8000/docs
