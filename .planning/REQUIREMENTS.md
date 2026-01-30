# Requirements: Transkribator v1.1 - Remote Server Optimization

**Defined:** 2026-01-30
**Core Value:** Точность распознавания русской речи на уровне WhisperTyping без существенной потери скорости

## Milestone v1.1 Requirements

Требования для оптимизации удалённого сервера транскрибации. Проблема: медленная работа, качество падает утром.

### SRV - Server Configuration

- [ ] **SRV-01**: TranscriberServer использует принудительный русский язык (`language="ru"` вместо `auto`)
- [ ] **SRV-02**: TranscriberServer использует оптимизированный backend (`sherpa/giga-am-v2-ru` вместо `whisper/base`)
- [ ] **SRV-03**: TranscriberServer включает VAD для удаления тишины (`vad_enabled=True`)
- [ ] **SRV-04**: TranscriberServer использует параметры quality profile (vad_threshold=0.3, min_silence=500, min_speech=300)
- [ ] **SRV-05**: TranscriberServer включает пост-обработку текста из Phase 3 (251 правило коррекции)

### AUDIO - Audio Encoding

- [ ] **AUDIO-01**: Клиент кодирует аудио в Opus формат перед отправкой (сжатие ~10x)
- [ ] **AUDIO-02**: Сервер поддерживает декодирование Opus формата
- [ ] **AUDIO-03**: Сохраняется поддержка WAV fallback для совместимости
- [ ] **AUDIO-04**: Размер аудио файла для 30 сек записи < 100 KB (было ~960 KB)

### CLIENT - Client Optimization

- [ ] **CLIENT-01**: VAD включён на клиенте для отрезания тишины ДО отправки на сервер
- [ ] **CLIENT-02**: Polling interval уменьшен с 2.0 сек до 0.5 сек (быстрее реакция)
- [ ] **CLIENT-03**: Добавлено логирование времени для каждого этапа (upload, transcription, download)
- [ ] **CLIENT-04**: Логи показывают размер файла и скорость передачи

### NET - Network & Stability

- [ ] **NET-01**: Сервер имеет автозапуск при старте системы
- [ ] **NET-02**: Serveo туннель автоматически восстанавливается при обрыве
- [ ] **NET-03**: Health check endpoint работает корректно
- [ ] **NET-04**: Логи сервера доступны для диагностики проблем
- [ ] **NET-05**: Fallback на локальную транскрибацию при недоступности сервера

## Future Requirements

Отложены на следующий milestone:

- **STREAM-01**: Streaming upload для параллельной записи и передачи
- **WS-01**: WebSocket вместо polling для realtime статуса
- **EDGE-01**: Edge-side обработка на сервере

## Out of Scope

| Feature | Reason |
|---------|--------|
| Полный рефакторинг архитектуры | Только оптимизация существующего |
| Изменение GUI | Только backend улучшения |
| Поддержка других языков | Русский приоритет |
| Новые модели | Оптимизация существующих |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SRV-01 | Phase 5 | Pending |
| SRV-02 | Phase 5 | Pending |
| SRV-03 | Phase 5 | Pending |
| SRV-04 | Phase 5 | Pending |
| SRV-05 | Phase 5 | Pending |
| AUDIO-01 | Phase 6 | Pending |
| AUDIO-02 | Phase 6 | Pending |
| AUDIO-03 | Phase 6 | Pending |
| AUDIO-04 | Phase 6 | Pending |
| CLIENT-01 | Phase 7 | Pending |
| CLIENT-02 | Phase 7 | Pending |
| CLIENT-03 | Phase 7 | Pending |
| CLIENT-04 | Phase 7 | Pending |
| NET-01 | Phase 8 | Pending |
| NET-02 | Phase 8 | Pending |
| NET-03 | Phase 8 | Pending |
| NET-04 | Phase 8 | Pending |
| NET-05 | Phase 8 | Pending |

**Coverage:** 19/19 requirements mapped (100%)

---
*Requirements defined: 2026-01-30*
*Milestone: v1.1 - Remote Server Optimization*
