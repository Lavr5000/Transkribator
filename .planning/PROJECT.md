# Transkribator Audio Quality Improvement

## What This Is

Улучшение качества транскрибации речи в приложении Transkribator для русского языка. Проект — гибридный Python-клиент (PyQt6) с опциональным удаленным сервером. Поддерживает несколько бэкендов (Whisper, Sherpa-ONNX, Podlodka).

## Core Value

**Точность распознавания русской речи на уровне WhisperTyping без существенной потери скорости.**

Если пользователь диктует текст или стихотворение — транскрипция должна быть слово-в-слово с оригиналом, сохраняя пунктуацию и структуру.

## Current Milestone: v1.1 Remote Server Optimization

**Goal:** Стабильная быстрая работа удалённого сервера транскрибации

**Target features:**
- Синхронизация параметров сервера с улучшениями Phase 1-4
- Opus сжатие аудио для быстрой передачи
- Оптимизация клиента (VAD, polling, логи)
- Стабильность подключения (автозапуск, Serveo, мониторинг)

## Requirements

### Validated

<!-- Existing capabilities shipped in v1.0 -->

- ✓ **Гибридная архитектура** — локальная транскрибация с автоматическим fallback (v1.0)
- ✓ **Multi-backend поддержка** — Whisper, Sherpa-ONNX, Podlodka-Turbo (v1.0)
- ✓ **Глобальный хоткей** — Ctrl+Shift+Space (v1.0)
- ✓ **Авто-вставка текста** — автоматическая вставка в активное окно (v1.0)
- ✓ **Whisper backend** — language="ru", beam_size=5, VAD optimization (v1.0, Phase 1)
- ✓ **Sherpa backend** — Transducer режим, правильные ONNX файлы (v1.0, Phase 1)
- ✓ **WebRTC Noise/Gain** — шумоподавление и AGC (v1.0, Phase 2)
- ✓ **Silero VAD** — для всех бэкендов (v1.0, Phase 2)
- ✓ **EnhancedTextProcessor** — 251 правило коррекции (v1.0, Phase 3)
- ✓ **Proper noun dictionary** — 779 entries (v1.0, Phase 3)
- ✓ **Quality profiles** — Fast/Balanced/Quality (v1.0, Phase 4)
- ✓ **User dictionary** — пользовательские коррекции (v1.0, Phase 4)
- ✓ **VAD settings UI** — настройка threshold и silence (v1.0, Phase 4)
- ✓ **Noise reduction settings UI** — WebRTC toggle и level (v1.0, Phase 4)

### Active

<!-- Current milestone v1.1 scope -->

- [ ] **SRV-01**: Сервер использует language="ru" вместо auto
- [ ] **SRV-02**: Сервер использует sherpa/giga-am-v2-ru вместо whisper/base
- [ ] **SRV-03**: Сервер включает VAD для удаления тишины
- [ ] **SRV-04**: Сервер использует параметры quality profile
- [ ] **SRV-05**: Сервер включает пост-обработку из Phase 3
- [ ] **AUDIO-01**: Клиент кодирует аудио в Opus формат (~10x сжатие)
- [ ] **AUDIO-02**: Сервер поддерживает декодирование Opus
- [ ] **AUDIO-03**: WAV fallback для совместимости
- [ ] **AUDIO-04**: Размер файла для 30 сек < 100 KB
- [ ] **CLIENT-01**: VAD на клиенте для отрезания тишины
- [ ] **CLIENT-02**: Polling interval уменьшен до 0.5 сек
- [ ] **CLIENT-03**: Логирование времени для каждого этапа
- [ ] **CLIENT-04**: Логи показывают размер файла и скорость
- [ ] **NET-01**: Автозапуск сервера при старте системы
- [ ] **NET-02**: Serveo туннель автоматически восстанавливается
- [ ] **NET-03**: Health check работает корректно
- [ ] **NET-04**: Логи сервера доступны
- [ ] **NET-05**: Fallback на локальную транскрибацию

### Out of Scope

- **Полный рефакторинг архитектуры** — только оптимизация существующего
- **Изменение GUI** — только backend улучшения
- **Поддержка других языков** — только русский приоритет
- **Новые модели** — оптимизация существующих
- **Streaming upload** — отложено на v1.2
- **WebSocket вместо polling** — отложено на v1.2

## Context

**Текущая архитектура:**
- Python 3.12, PyQt6 GUI
- Бэкенды: faster-whisper, sherpa-onnx (GigaAM v2)
- Клиент-сервер с Tailscale + Serveo.net fallback
- Удалённый сервер: FastAPI на Windows

**Проблема v1.1:** Медленная работа удалённого сервера, качество падает утром

**Диагностика показала:**
- transcriber_wrapper.py использует СТАРЫЕ параметры (language="auto", backend="whisper")
- WAV формат без сжатия = большие файлы = медленный upload
- Polling interval 2 сек добавляет задержку

## Constraints

- **Speed**: Транскрибация должна быть в реальном времени или быстрее (RTF < 1.0)
- **Compatibility**: Должно работать на Windows без GPU
- **Memory**: Модели в RAM (< 4GB)
- **Dependencies**: Минимизировать новые тяжелые зависимости
- **Architecture**: Сохранить клиент-сервер гибрид

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Приоритет русского языка | Пользователь использует для русского | ✓ Confirmed |
| Opus сжатие для аудио | 10x уменьшение размера файлов | — Pending |
| VAD на клиенте | Меньше данных = быстрее upload | — Pending |
| Sherpa на сервере | 10x быстрее для русского | — Pending |
| Автозапуск сервера | Стабильность подключения | — Pending |

---
*Last updated: 2026-01-30 after milestone v1.1 initialization*
