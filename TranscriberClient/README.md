# Remote Transcriber Client

CLI клиент для удаленной транскрибации аудиофайлов.

## Установка

```bash
cd C:\Users\user\.claude\0 ProEKTi\Transkribator\TranscriberClient
pip install -r requirements.txt
```

## Использование

### Базовое использование

```bash
python client.py audio.mp3
```

### Проверка состояния сервера

```bash
python client.py --health
```

### Справка

```bash
python client.py --help
```

## Поддерживаемые форматы

- `.mp3` - MP3 audio
- `.wav` - WAV audio
- `.m4a` - M4A audio
- `.ogg` - OGG audio
- `.flac` - FLAC audio
- `.aac` - AAC audio
- `.wma` - WMA audio

## Пример работы

```bash
$ python client.py my_recording.mp3

==================================================
REMOTE TRANSCRIBER
==================================================

[1/3] Загрузка файла: my_recording.mp3
      Размер: 2.45 MB
      ✓ Task ID: abc-123-def
      Файл: my_recording.mp3
[2/3] Транскрибация...
Прогресс: 10сек... 20сек... 30сек...
      ✓ Готово! (за 32.5 сек)
[3/3] Получение результата...
      ✓ Сохранено: downloads\my_recording.txt

==================================================
РЕЗУЛЬТАТ ТРАНСКРИБАЦИИ
==================================================

Привет, это пример транскрибации. Сервер работает отлично!

==================================================

Статистика: 9 слов, 65 символов
Файл сохранён: downloads/my_recording.txt
```

## Настройка

### Изменить URL сервера

Отредактируйте `client.py`:

```python
SERVER_URL = "http://your-server:8000"
```

## Структура

```
TranscriberClient/
├── client.py         # CLI клиент
├── requirements.txt  # Зависимости
└── downloads/        # Скачанные результаты (создаётся автоматически)
```

## Troubleshooting

### Ошибка соединения

```
✗ Не удалось подключиться к серверу
```

**Решение:**
1. Проверьте что удаленный ПК включен
2. Проверьте состояние сервера: `python client.py --health`
3. Проверьте что SSH туннель работает на удаленном ПК

### Ошибка загрузки файла

```
✗ Ошибка загрузки: 500
```

**Решение:**
1. Проверьте логи на удаленном ПК: `C:\Users\User1\Desktop\serveo-tunnel.log`
2. Убедитесь что TranscriberServer запущен

### Долгая транскрибация

Транскрибация файла размером 1 MB обычно занимает 10-30 секунд на CPU.

Для ускорения используйте GPU (если доступен) в `transcriber_wrapper.py`:

```python
self.transcriber = Transcriber(
    device="cuda",  # вместо "auto"
)
```
