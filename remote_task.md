# ЗАДАЧА: Перезапустить сервер транскрибации

## Проблема
Сервер на порту 8000 не отвечает. Нужно запустить его.

## Решение

Выполните в терминале (PowerShell или CMD):

```batch
cd C:\Users\User1\Desktop\Transcriber\TranscriberServer
python -m uvicorn server:app --host 0.0.0.0 --port 8000
```

## Проверка
После запуска сервер должен отвечать на http://localhost:8000/health

## Автозапуск (опционально)
Для постоянной работы добавьте в автозагрузку Windows:
- C:\Users\User1\Desktop\AUTOSTART_TRANSKRIBER.bat
