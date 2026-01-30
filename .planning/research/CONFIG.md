# Configuration Diagnostic Report

## Текущие параметры на сервере

### TranscriberServer/transcriber_wrapper.py

```python
self.transcriber = Transcriber(
    backend="whisper",          # ❌ СТАРОЕ
    model_size="base",          # ❌ СТАРОЕ
    device="auto",
    language="auto",            # ❌ ❌ КРИТИЧЕСКАЯ ПРОБЛЕМА
    enable_post_processing=True
)
```

**Проблемы:**
1. `backend="whisper"` вместо `sherpa` - ~10x медленнее для русского
2. `model_size="base"` вместо `giga-am-v2-ru` - не оптимизирован
3. `language="auto"` вместо `"ru"` - **лишние вычисления автоопределения**
4. **Нет VAD параметров** - обрабатывается вся тишина

### Оптимальные параметры (из Phase 1-4)

```python
self.transcriber = Transcriber(
    backend="sherpa",                    # ✅ 10x быстрее
    model_size="giga-am-v2-ru",          # ✅ Специализирован для русского
    device="auto",
    language="ru",                       # ✅ Принудительно русский
    enable_post_processing=True,
    # VAD параметры (Phase 2):
    vad_enabled=True,                    # ✅ Удаление тишины
    vad_threshold=0.3,                   # ✅ Quality profile
    min_silence_duration_ms=500,         # ✅ Quality profile
    min_speech_duration_ms=300,          # ✅ Для русского языка
    # User dictionary (Phase 4):
    user_dictionary=[],                   # ✅ Пользовательские коррекции
)
```

## WhisperBackend (локальный) - уже обновлён!

```python
# src/backends/whisper_backend.py:41
language: str = "ru",  # ✅ Already fixed!
```

**Клиент уже использует правильные параметры, но сервер - НЕТ!**

## SherpaBackend

Нужно проверить - но должен быть уже обновлён из Phase 1-2.

## RemoteTranscriptionClient

```python
# src/remote_client.py
timeout_upload: float = 60.0     # ✅ Достаточно
timeout_poll: float = 10.0       # ✅ Достаточно
check_interval = 2.0              # ❌ Можно 0.5 сек
```

## Сравнение: старые vs новые параметры

| Параметр | Старое | Новое | Эффект |
|----------|--------|-------|--------|
| language | `auto` | `ru` | +15-30% точности, +5-10% скорости |
| backend | `whisper/base` | `sherpa/giga-am-v2-ru` | +10x скорость |
| vad_enabled | False | True | +5-15% точности, +20-40% скорость (меньше тишины) |
| model_size | base | giga-am-v2-ru | Специализирован для русского |

## Стерео vs Моно

Нужно проверить в `audio_recorder.py`:
- `channels: int = 1` - моно ✅
- `sample_rate: int = 16000` - стандарт для Speech-to-Text ✅

## Выводы

1. **КРИТИЧНО:** `transcriber_wrapper.py` на сервере использует СТАРЫЕ параметры
2. **КРИТИЧНО:** `language="auto"` - лишние вычисления и хуже качество для русского
3. **ВАЖНО:** Нет VAD - обрабатывается тишина
4. **ЖЕЛАТЕЛЬНО:** `backend="whisper"` вместо оптимизированного Sherpa
