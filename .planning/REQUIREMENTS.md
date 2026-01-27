# Requirements: Transkribator Audio Quality Improvement

**Defined:** 2026-01-27
**Core Value:** Точность распознавания русской речи на уровне WhisperTyping без существенной потери скорости

## v1 Requirements

Требования для улучшения качества транскрибации до уровня WhisperTyping. Каждое требование отображается на фазу roadmap.

### Model Optimization

- [ ] **MODEL-01**: Whisper backend принудительно использует `language="ru"` вместо auto-detection
- [ ] **MODEL-02**: Whisper backend использует `beam_size=5` (качество) или `beam_size=2` (баланс) вместо текущего `beam_size=1`
- [ ] **MODEL-03**: Whisper backend использует `temperature=0.0` для детерминированной декодировки
- [ ] **MODEL-04**: Whisper backend использует `no_speech_threshold=0.6` для предотвращения галлюцинаций на тишине
- [ ] **MODEL-05**: Sherpa backend исправлен с CTC на Transducer режим (`from_nemo_transducer`)
- [ ] **MODEL-06**: Sherpa backend использует `max_active_paths=4` для оптимальной точности
- [ ] **MODEL-07**: Sherpa backend использует правильные файлы модели (encoder.int8.onnx, decoder.onnx, joiner.onnx)
- [ ] **MODEL-08**: VAD параметры оптимизированы для русского языка (min_speech_duration_ms=300, speech_pad_ms=400)

### Audio Processing

- [ ] **AUDIO-01**: AudioRecorder интегрирован с WebRTC Noise/Gain для шумоподавления
- [ ] **AUDIO-02**: Текущий 20x software gain заменён на адаптивный AGC от WebRTC
- [ ] **AUDIO-03**: Шумоподавление применяется ДО VAD для лучшей точности детекции речи
- [ ] **AUDIO-04**: WebRTC обработка работает в реальном времени (<10ms latency)
- [ ] **AUDIO-05**: Fallback на noisereduce если WebRTC недоступен

### Voice Activity Detection

- [ ] **VAD-01**: Silero VAD интегрирован в SherpaBackend
- [ ] **VAD-02**: VAD работает для всех бэкендов (Whisper, Sherpa, Podlodka)
- [ ] **VAD-03**: VAD параметры настраиваемые через config (threshold, min_silence_duration_ms)
- [ ] **VAD-04**: VAD визуализация в UI (индикатор записи речи)

### Text Post-Processing

- [ ] **POST-01**: EnhancedTextProcessor расширен с 50 до 100+ правил коррекции
- [ ] **POST-02**: Добавлены фонетические коррекции (б↔п, в↔ф, г↔к, д↔т, з↔с)
- [ ] **POST-03**: Добавлены морфологические коррекции (род, падеж, спряжение)
- [ ] **POST-04**: Словарь имен собственных (1000-5000 entries: Москва, Denis, Россия, Сергей...)
- [ ] **POST-05**: Капитализация после пунктуации улучшена
- [ ] **POST-06**: Punctuation restoration работает для всех бэкендов
- [ ] **POST-07**: Пост-обработка адаптивная для Whisper (есть пунктуация) vs Sherpa (нет пунктуации)

### Configuration & UX

- [ ] **CFG-01**: Quality profiles в настройках (Fast/Balanced/Quality)
- [ ] **CFG-02**: Пользовательский словарь коррекций (добавление своих слов/терминов)
- [ ] **CFG-03**: Настройки VAD доступны в UI
- [ ] **CFG-04**: Настройки noise reduction доступны в UI
- [ ] **CFG-05**: Выбор модели доступен в UI (tiny/base/small/medium/large-v3-turbo)

### Testing & Validation

- [ ] **TEST-01**: A/B тестирование до/после улучшений на одном аудио
- [ ] **TEST-02**: Измерение WER (Word Error Rate) до/после
- [ ] **TEST-03**: Измерение CER (Character Error Rate) до/после
- [ ] **TEST-04**: Сравнение с WhisperTyping на том же аудио
- [ ] **TEST-05**: Измерение RTF (Real-Time Factor) для проверки скорости

### Server Synchronization

- [ ] **SRV-01**: Улучшения синхронизированы между клиентом и сервером
- [ ] **SRV-02**: TranscriberServer использует те же параметры модели
- [ ] **SRV-03**: RemoteClient корректно работает с улучшенным pipeline

## v2 Requirements

Отложены до будущей версии. Отслеживаются, но не входят в текущий roadmap.

### Advanced Features

- **ADV-01**: Russian-fine-tuned Whisper model (опциональная загрузка)
- **ADV-02**: LLM-based error correction (ручной триггер)
- **ADV-03**: Morphological POS-tagger для русского языка
- **ADV-04**: Whisper hallucination detection и фильтрация

## Out of Scope

Явно исключено. Документировано для предотвращения scope creep.

| Feature | Reason |
|---------|--------|
| RNNoise | Нет Python bindings, только C++ реализация |
| Полный рефакторинг архитектуры | Только целевые улучшения качества |
| Смена на только Whisper бэкенд | Sherpa быстрее для русского, нужен баланс |
| Поддержка других языков | Только русский приоритет в v1 |
| Изменение GUI дизайна | Улучшения только backend-логики |
| Real-time VAD при записи | VAD только для транскрибации и визуализации |

## Traceability

Какие фазы покрывают какие требования. Обновляется при создании roadmap.

| Requirement | Phase | Status |
|-------------|-------|--------|
| MODEL-01 | Phase 1 | Pending |
| MODEL-02 | Phase 1 | Pending |
| MODEL-03 | Phase 1 | Pending |
| MODEL-04 | Phase 1 | Pending |
| MODEL-05 | Phase 1 | Pending |
| MODEL-06 | Phase 1 | Pending |
| MODEL-07 | Phase 1 | Pending |
| MODEL-08 | Phase 1 | Pending |
| AUDIO-01 | Phase 2 | Pending |
| AUDIO-02 | Phase 2 | Pending |
| AUDIO-03 | Phase 2 | Pending |
| AUDIO-04 | Phase 2 | Pending |
| AUDIO-05 | Phase 2 | Pending |
| VAD-01 | Phase 2 | Pending |
| VAD-02 | Phase 2 | Pending |
| VAD-03 | Phase 2 | Pending |
| VAD-04 | Phase 2 | Pending |
| POST-01 | Phase 3 | Pending |
| POST-02 | Phase 3 | Pending |
| POST-03 | Phase 3 | Pending |
| POST-04 | Phase 3 | Pending |
| POST-05 | Phase 3 | Pending |
| POST-06 | Phase 3 | Pending |
| POST-07 | Phase 3 | Pending |
| CFG-01 | Phase 4 | Pending |
| CFG-02 | Phase 4 | Pending |
| CFG-03 | Phase 4 | Pending |
| CFG-04 | Phase 4 | Pending |
| CFG-05 | Phase 4 | Pending |
| TEST-01 | Phase 1 | Pending |
| TEST-02 | Phase 1 | Pending |
| TEST-03 | Phase 1 | Pending |
| TEST-04 | Phase 1 | Pending |
| TEST-05 | Phase 1 | Pending |
| SRV-01 | Phase 1 | Pending |
| SRV-02 | Phase 1 | Pending |
| SRV-03 | Phase 1 | Pending |

**Coverage:**
- v1 requirements: 43 total
- Mapped to phases: 43
- Unmapped: 0 ✓

---
*Requirements defined: 2026-01-27*
*Last updated: 2026-01-27 after roadmap creation*
