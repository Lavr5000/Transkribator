# Установка Sherpa на сервере 192.168.31.9

## Инструкция для выполнения на УДАЛЕННОМ ПК (192.168.31.9)

### Предварительные требования:
- Удаленный ПК должен быть включен
- Доступ к рабочему столу (через RDP или физически)

---

## Шаг 1: Проверить текущую версию Python

Откройте **Command Prompt** или **PowerShell** на удаленном ПК и выполните:

```batch
python --version
```

Ожидается: Python 3.10.x или выше

---

## Шаг 2: Установить sherpa-onnx

```batch
pip install sherpa-onnx
```

Ожидаемое время: 2-5 минут

---

## Шаг 3: Проверить установку

```batch
python -c "import sherpa_onnx; print('sherpa-onnx version:', sherpa_onnx.__version__)"
```

Ожидается: `sherpa-onnx version: 1.x.x`

---

## Шаг 4: Скачать модель GigaAM

**ВАЖНО:** Sherpa требует модельные файлы. Создайте папку для модели:

```batch
mkdir C:\Users\Denis\TranscriberServer\models
cd C:\Users\Denis\TranscriberServer\models
```

Затем скачайте модель (один из вариантов):

### Вариант А: Скачать вручную
1. Откройте браузер на удаленном ПК
2. Перейдите на: https://github.com/k2-fsa/sherpa-onnx/releases
3. Скачайте `sherpa-onnx-gigaam-v2-russian-paraformer` или аналогичную модель для русского
4. Распакуйте в `C:\Users\Denis\TranscriberServer\models\gigaam-v2`

### Вариант Б: Через PowerShell (если доступно)
```powershell
cd C:\Users\Denis\TranscriberServer\models
# Прямая ссылка на модель (замените на актуальную)
Invoke-WebRequest -Uri "https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.0.0/sherpa-onnx-gigaam-v2-russian-paraformer.tar.bz2" -OutFile "model.tar.bz2"
tar -xf model.tar.bz2
```

---

## Шаг 5: Обновить transcriber_wrapper.py

Откройте файл:
```
C:\Users\Denis\TranscriberServer\transcriber_wrapper.py
```

Замените содержимое на:

```python
#!/usr/bin/env python3
"""
Transcriber wrapper for Transcriber Server with Sherpa backend.
"""

import sys
import os

# Add src to path
server_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(server_dir, 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from transcriber import Transcriber

# Configure Sherpa with GigaAM model
transcriber = Transcriber(
    backend="sherpa",
    model_size="giga-am-v2-ru",
    device="cpu",  # или "cuda" если есть NVIDIA GPU
    language="ru",
    enable_post_processing=True
)

print("Transcriber initialized successfully")
print(f"Backend: {transcriber.backend}")
print(f"Model: {transcriber.model_size}")
print("Server ready to accept requests")
```

---

## Шаг 6: Остановить старый сервер

Откройте **Task Manager** (Ctrl+Shift+Esc), найдите все процессы `python.exe` и завершите их.

ИЛИ через Command Prompt:
```batch
taskkill /F /IM python.exe
```

---

## Шаг 7: Запустить сервер

```batch
cd C:\Users\Denis\TranscriberServer
python server.py
```

Должно появиться:
```
INFO:     Started server process [PID]
INFO:     Waiting for application startup.
Transcriber initialized successfully
Backend: sherpa
Model: giga-am-v2-ru
Server ready to accept requests
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## Шаг 8: Проверить health endpoint

На **НОУТБУКЕ** откройте Command Prompt:

```batch
curl http://192.168.31.9:8000/health
```

ИЛИ через PowerShell:
```powershell
Invoke-RestMethod -Uri "http://192.168.31.9:8000/health" | ConvertTo-Json
```

Ожидается:
```json
{
  "status": "healthy",
  "transcriber_loaded": true  ← ВАЖНО: должно быть true!
}
```

---

## Если transcriber_loaded: false

### Проблема 1: Модель не найдена
**Решение:** Убедитесь что модель скачана и путь правильный

### Проблема 2: sherpa-onnx не установлен
**Решение:** Повторите Шаг 2

### Проблема 3: Ошибка импорта
**Решение:** Проверьте `src/` папку на сервере. Должно быть:
- `C:\Users\Denis\TranscriberServer\src\transcriber.py`
- `C:\Users\Denis\TranscriberServer\src\config.py`
- и т.д.

Если папки `src/` нет - скопируйте её с ноутбука:
```batch
# На ноутбуке:
robocopy "C:\Users\user\.claude\0 ProEKTi\Transkribator\src" "\\192.168.31.9\C$\Users\Denis\TranscriberServer\src" /E
```

---

## После успешной установки

1. Закройте окно с сервером (оно останется в фоне)
2. На **НОУТБУКЕ** протестируйте:
   - F9 → скажите 3-5 секунд → F9
   - Должен появиться **🌐** (глобус) - удаленная транскрибация!
   - Транскрибация будет быстрой (3-10 секунд)

3. Проверьте `debug.log` на ноутбуке:
   ```batch
   tail -20 C:\Users\user\.claude\0 ProEKTi\Transkribator\debug.log
   ```

   Должно быть:
   ```
   [DEBUG] Mode: REMOTE (is_remote=True)
   [DEBUG] Mode label shown: 🌐
   ```

---

## Альтернатива: Использовать Whisper (проще)

Если Sherpa не работает - можно использовать Whisper:

### Измените transcriber_wrapper.py на сервере:

```python
transcriber = Transcriber(
    backend="whisper",  # Вместо sherpa
    model_size="base",  # Вместо giga-am-v2-ru
    device="cpu",
    language="ru",
    enable_post_processing=True
)
```

Whisper тоже хорошо работает с русским языком и не требует скачивания отдельной модели (скачается автоматически при первом запуске).

---

## Проблемы и решения

| Проблема | Решение |
|----------|---------|
| Permission denied (SSH) | Выполняйте команды прямо на удаленном ПК |
| sherpa-onnx not found | `pip install sherpa-onnx` |
| Model not found | Скачайте модель GigaAM вручную |
| transcriber_loaded: false | Проверьте логи сервера, модель должна загрузиться |
| Server not accessible | Проверьте firewall: `netsh advfirewall firewall add rule name="Transcriber" dir=in action=allow protocol=TCP localport=8000` |
| Src folder missing | Скопируйте `src/` с ноутбука на сервер |

---

## Контакты для помощи

Если что-то не работает - проверьте:
1. Python версии 3.10+
2. Установлен sherpa-onnx
3. Модель скачана
4. src/ папка существует
5. Firewall разрешает порт 8000
6. Сервер запущен и не выдает ошибок

**Удачи!** 🚀
