# Remote Transcriber Server

FastAPI сервер для удаленной транскрибации аудиофайлов через WhisperTyping.

## Установка

### 1. Установить зависимости

```bash
cd C:\Users\user\.claude\0 ProEKTi\Transkribator\TranscriberServer
pip install -r requirements.txt
```

### 2. Протестировать локально

```bash
python -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload
```

Проверить: http://127.0.0.1:8000/docs

## Использование

### Запуск сервера

```bash
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

### API Endpoints

- `POST /transcribe` - Загрузить аудиофайл для транскрибации
- `GET /status/{task_id}` - Проверить статус
- `GET /result/{task_id}` - Скачать результат
- `GET /health` - Проверка состояния

### Пример запроса

```bash
curl -X POST "http://127.0.0.1:8000/transcribe" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@audio.mp3"
```

Ответ:
```json
{
  "task_id": "abc-123-def",
  "status": "processing",
  "filename": "audio.mp3"
}
```

## Интеграция с автозапуском

Добавить в `C:\Users\User1\Desktop\AUTOSTART_SERVEO.bat`:

```batch
cd C:\Users\user\.claude\0 ProEKTi\Transkribator\TranscriberServer
start /B python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

## Структура

```
TranscriberServer/
├── server.py              # FastAPI сервер
├── transcriber_wrapper.py # Обёртка над Transcriber
├── requirements.txt       # Зависимости
├── uploads/               # Входящие файлы
└── results/               # Результаты транскрибации
```

## Логирование

Логи сохраняются в консоль. Для записи в файл добавьте в `server.py`:

```python
import logging
logging.basicConfig(filename='server.log', level=logging.INFO)
```
