# Remote Transcriber Client

CLI клиент для удаленной транскрибации аудиофайлов.

## Установка

```bash
cd TranscriberClient
pip install -r requirements.txt
```

## Настройка

Адреса серверов и ключ задаются переменными окружения (в коде адресов нет):

```bash
set TRANSKRIBATOR_SERVERS=http://<server-host>:8000
set TRANSCRIBER_API_KEY=<тот же ключ, что на сервере>
```

**Безопасность.** Трафик — обычный HTTP: ключ и аудио видны всем на пути.
Поэтому `http://` принимается только для loopback / LAN (RFC1918) /
Tailscale (100.64.0.0/10) адресов — рекомендуемый способ удалённого доступа
— Tailscale. Прочие адреса требуют `TRANSKRIBATOR_ALLOW_INSECURE=1`
(не рекомендуется). Не публикуйте порт через публичные туннели (serveo,
ngrok): оператор реле видит ключ и записи речи.

## Использование

```bash
python client.py audio.mp3      # транскрибировать файл
python client.py --health       # проверка сервера
python client.py --help         # справка
```

## Поддерживаемые форматы

`.mp3` `.wav` `.m4a` `.ogg` `.flac` `.aac` `.wma`

## Структура

```
TranscriberClient/
├── client.py         # CLI клиент
├── requirements.txt  # Зависимости
└── downloads/        # Скачанные результаты (создаётся автоматически)
```

## Troubleshooting

**Ошибка соединения** — проверьте, что удалённый ПК включён, сервер запущен
(`python server.py` в TranscriberServer), `TRANSKRIBATOR_SERVERS` указывает
на правильный адрес, `python client.py --health` отвечает.

**Долгая транскрибация** — файл 1 MB обычно занимает 10-30 секунд на CPU.
