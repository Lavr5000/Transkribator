# 🚀 Установка Sherpa - 3 простых шага

## Текущий статус:
- ✅ **GUI работает** (показывает 🏠 при локальной транскрибации)
- ✅ **src/ скопирован** на сервер (34 файла)
- ✅ **Сервер работает** но `transcriber_loaded: false`
- ❌ **Нужна установка Sherpa** или переключение на Whisper

---

## 🎯 Решение (3 шага, 3 минуты):

### ШАГ 1: Подключиться к удаленному ПК

Откройте на ноутбуке:
```batch
mstsc /v:REDACTED-LAN
```

Или зайдите физически

---

### ШАГ 2: Скопировать файл

С ноутбука скопируйте файл:
```
C:\Users\user\.claude\REDACTED-PATH\Transkribator\TranscriberServer\ONE_CLICK_INSTALL.bat
```

На удаленный ПК в:
```
C:\Users\Denis\TranscriberServer\ONE_CLICK_INSTALL.bat
```

---

### ШАГ 3: Запустить

На удаленном ПК дважды кликните `ONE_CLICK_INSTALL.bat`

**Скрипт автоматически:**
1. Проверит Python и src/
2. Установит sherpa-onnx (2-5 минут)
3. Настроит transcriber_wrapper.py
4. Перезапустит сервер
5. Проверит health

**В конце покажет:**
- ✅ **SUCCESS!** - если работает
- ⚠️ **WARNING:** - если нужна ручная настройка

---

## ✅ После успешной установки:

На **НОУТБУКЕ**:

1. **F9** → скажите 3-5 секунд → **F9**
2. **Должен появиться 🌐 (глобус)** в верхнем правом углу!
3. Транскрибация будет быстрой (3-10 секунд)

---

## ❓ Если не работает:

### Проблема: transcriber_loaded: false

**Решение:** Используйте Whisper (работает 100%)

На удаленном ПК в командной строке:
```batch
cd C:\Users\Denis\TranscriberServer
powershell -Command "(gc transcriber_wrapper.py) -replace 'backend=\"sherpa\"', 'backend=\"whisper\"' -replace 'model_size=\"giga-am-v2-ru\"', 'model_size=\"base\"' | Set-Content transcriber_wrapper.py"
taskkill /F /IM python.exe
timeout /t 2
start /B python server.py
timeout /t 5
curl http://REDACTED-LAN:8000/health
```

Должно показать `"transcriber_loaded": true`

---

## 📞 Что нужно сделать прямо сейчас:

1. Подключиться к REDACTED-LAN (RDP или физически)
2. Скопировать `ONE_CLICK_INSTALL.bat` туда
3. Запустить `ONE_CLICK_INSTALL.bat`
4. Дождаться завершения
5. Протестировать на ноутбуке (F9 → сказать → F9)

**Всё! Это займет 3 минуты.** ⏱️
