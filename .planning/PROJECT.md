# Transkribator Audio Quality Improvement

## What This Is

Улучшение качества транскрибации речи в приложении Transkribator для русского языка. Проект — гибридный Python-клиент (PyQt6) с опциональным удаленным сервером. Поддерживает несколько бэкендов (Whisper, Sherpa-ONNX, Podlodka).

## Core Value

**Точность распознавания русской речи на уровне WhisperTyping без существенной потери скорости.**

Если пользователь диктует текст или стихотворение — транскрипция должна быть слово-в-слово с оригиналом, сохраняя пунктуацию и структуру.

## Requirements

### Validated

<!-- Existing capabilities from codebase analysis -->

- ✓ **Гибридная архитектура** — локальная транскрибация с автоматическим fallback на удаленный сервер (существующая)
- ✓ **Multi-backend поддержка** — Whisper, Sherpa-ONNX, Podlodka-Turbo (существующая)
- ✓ **Глобальный хоткей** — Ctrl+Shift+Space для записи (существующая)
- ✓ **Авто-вставка текста** — автоматическая вставка в активное окно (существующая)
- ✓ **VAD в Whisper** — Voice Activity Detection для Whisper бэкенда (существующая)
- ✓ **Post-processing** — базовая коррекция ошибок для русского (существующая)
- ✓ **History Manager** — история транскрибаций (существующая)
- ✓ **Software gain** — mic_boost=20.0 для усиления тихих микрофонов (существующая)

### Active

<!-- Current scope — what we're building toward -->

- [ ] **VAD-01**: VAD для Sherpa бэкенда (как в Whisper) — удаление тишины до транскрибации
- [ ] **POST-01**: EnhancedTextProcessor для всех бэкендов — пунктуация через deepmultilingualpunctuation
- [ ] **POST-02**: Расширенные коррекции для русского языка — исправление CTC-ошибок Sherpa
- [ ] **AUDIO-01**: Шумоподавление на входе — noise reduction для улучшения качества аудио
- [ ] **AUDIO-02**: VAD на этапе записи — trimming тишины в начале/конце записи
- [ ] **MODEL-01**: Оптимизированные параметры моделей — beam_size, temperature, language detection
- [ ] **QUAL-01**: Метрики качества — измерение точности (WER) до/после улучшений
- [ ] **QUAL-02**: A/B тестирование — сравнение с WhisperTyping на одном аудио
- [ ] **SRV-01**: Синхронизация улучшений — сервер и клиент используют одинаковые алгоритмы

### Out of Scope

<!-- Explicit boundaries -->

- **Смена бэкенда на только Whisper** — Sherpa быстрее для русского, нужен баланс
- **Полный рефакторинг архитектуры** — только целевые улучшения качества
- **Поддержка других языков** — только русский приоритет
- **Изменение GUI** — улучшения только backend-логики
- **Новые модели** — оптимизация существующих (GigaAM v2, Whisper large-v3)

## Context

**Текущая архитектура:**
- Python 3.12, PyQt6 GUI
- Бэкенды: faster-whisper, sherpa-onnx (GigaAM v2)
- Клиент-сервер с автоматическим fallback
- Путь: `C:\Users\user\.claude\0 ProEKTi\Transkribator`

**Проблема (на примере стихотворения Исаковского):**
```
Sherpa: "торопинка или сок, более каждый колоссок, небо море, глубое..."
Whisper: "тропинка или сок в поле каждой колоссок. Нево в море, губо..."
Эталон: "И тропинка, и лесок, В поле – каждый колосок! Речка, небо голубое..."
```

**Сравнение с WhisperTyping (референс):**
- WhisperTyping использует EnhancedTextProcessor с deepmultilingualpunctuation
- VAD с 200ms минимальной тишиной
- Language-specific corrections для русского
- Sherpa-ONNX с GigaAM v2 как основной бэкенд

**Технические детали из анализа кода:**
- VAD реализован только в WhisperBackend (`vad_filter=True`)
- SherpaBackend не имеет VAD — обрабатывает всё аудио целиком
- EnhancedTextProcessor существует, но используется только для Sherpa
- Аудио: 16kHz mono, software gain 20x, hard clipping
- Нет noise reduction, AGC, нормализации

## Constraints

- **Speed**: Транскрибация должна быть в реальном времени или быстрее (RTF < 1.0)
- **Compatibility**: Должно работать на Windows без GPU
- **Memory**: Модели должны загружаться в RAM (< 4GB для CPU inference)
- **Dependencies**: Минимизировать новые тяжелые зависимости
- **Architecture**: Сохранить клиент-сервер гибрид

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Приоритет русского языка | Пользователь использует для русского | ✓ Confirmed |
| Баланс скорости и качества | Пользователь выбрал "Баланс" | — Pending |
| VAD для всех бэкендов | Sherpa сейчас без VAD, страдает качество | — Pending |
| Enhanced post-processing | WhisperTyping использует успешно | — Pending |

---
*Last updated: 2026-01-27 after initialization*
