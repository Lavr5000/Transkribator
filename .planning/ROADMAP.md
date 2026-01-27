# Roadmap: Transkribator Audio Quality Improvement

## Overview

Улучшение точности распознавания русской речи в приложении Transkribator от текущего уровня (много ошибок, Sherpa выводит "торопинка или сок") до уровня WhisperTyping (слово-в-слово с оригиналом, сохраняя пунктуацию). Путь качественных улучшений через 4 фазы: исправление критических багов в моделях, внедрение шумоподавления, улучшение пост-обработки текста и добавление продвинутых настроек.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Critical Bug Fixes** - Исправление параметров моделей и архитектуры Sherpa-ONNX
- [ ] **Phase 2: Noise Reduction + VAD** - Внедрение шумоподавления и Voice Activity Detection
- [ ] **Phase 3: Text Processing Enhancement** - Расширенная пост-обработка русской речи
- [ ] **Phase 4: Advanced Features** - Профили качества и пользовательские настройки

## Phase Details

### Phase 1: Critical Bug Fixes

**Goal**: Модели Whisper и Sherpa используют правильные параметры и архитектуру, что даёт 15-30% улучшение точности распознавания

**Depends on**: Nothing (first phase)

**Requirements**: MODEL-01, MODEL-02, MODEL-03, MODEL-04, MODEL-05, MODEL-06, MODEL-07, MODEL-08, TEST-01, TEST-02, TEST-03, TEST-04, TEST-05, SRV-01, SRV-02, SRV-03

**Success Criteria** (what must be TRUE):
1. Whisper backend принудительно использует русский язык (`language="ru"`) вместо auto-detection
2. Whisper backend использует beam_size=5 (качество) или beam_size=2 (баланс) вместо beam_size=1
3. Sherpa backend исправлен с CTC на Transducer режим и использует правильные ONNX файлы модели
4. VAD параметры оптимизированы для русского языка (min_speech_duration_ms=300, speech_pad_ms=400)
5. Клиент и сервер используют идентичные параметры моделей (синхронизированы)
6. A/B тесты показывают измеримое улучшение WER/CER по сравнению с текущей версией

**Plans**: TBD (will be determined during planning)

Plans:
- [ ] 01-01: Fix Whisper backend parameters (language, beam_size, temperature, no_speech_threshold)
- [ ] 01-02: Fix Sherpa backend architecture (CTC → Transducer, max_active_paths, model files)
- [ ] 01-03: Optimize VAD parameters for Russian language
- [ ] 01-04: Implement testing framework (WER, CER, RTF measurements)
- [ ] 01-05: Synchronize improvements between client and server

### Phase 2: Noise Reduction + VAD

**Goal**: Аудио на входе очищено от шума, тишина удалена до транскрибации, что даёт 5-15% улучшение WER

**Depends on**: Phase 1

**Requirements**: AUDIO-01, AUDIO-02, AUDIO-03, AUDIO-04, AUDIO-05, VAD-01, VAD-02, VAD-03, VAD-04

**Success Criteria** (what must be TRUE):
1. AudioRecorder применяет WebRTC Noise/Gain для шумоподавления в реальном времени (<10ms latency)
2. Текущий 20x software gain заменён на адаптивный AGC от WebRTC
3. Шумоподавление применяется ДО VAD для лучшей точности детекции речи
4. Silero VAD интегрирован в SherpaBackend и работает для всех бэкендов (Whisper, Sherpa, Podlodka)
5. VAD параметры настраиваются через config (threshold, min_silence_duration_ms)
6. VAD визуализируется в UI (индикатор записи речи)

**Plans**: TBD (will be determined during planning)

Plans:
- [ ] 02-01: Integrate WebRTC Noise/Gain into AudioRecorder
- [ ] 02-02: Replace 20x software gain with adaptive AGC
- [ ] 02-03: Integrate Silero VAD into SherpaBackend
- [ ] 02-04: Implement VAD for all backends (Whisper, Sherpa, Podlodka)
- [ ] 02-05: Add VAD visualization in UI

### Phase 3: Text Processing Enhancement

**Goal**: Пост-обработка текста исправляет 100+ типичных ошибок русской речи, включая имена собственные

**Depends on**: Phase 2

**Requirements**: POST-01, POST-02, POST-03, POST-04, POST-05, POST-06, POST-07

**Success Criteria** (what must be TRUE):
1. EnhancedTextProcessor расширен с 50 до 100+ правил коррекции для русского языка
2. Фонетические коррекции применяются (б↔п, в↔ф, г↔к, д↔т, з↔с)
3. Морфологические коррекции работают (род, падеж, спряжение)
4. Словарь имен собственных содержит 1000-5000 entries (Москва, Denis, Россия, Сергей...)
5. Капитализация после пунктуации улучшена (заглавная после ".", "!", "?")
6. Punctuation restoration работает для всех бэкендов
7. Пост-обработка адаптивна для Whisper (есть пунктуация) vs Sherpa (нет пунктуации)

**Plans**: TBD (will be determined during planning)

Plans:
- [ ] 03-01: Expand EnhancedTextProcessor from 50 to 100+ correction rules
- [ ] 03-02: Add phonetic corrections for Russian language
- [ ] 03-03: Add morphological corrections (gender, case, conjugation)
- [ ] 03-04: Create proper noun dictionary (1000-5000 entries)
- [ ] 03-05: Improve capitalization after punctuation
- [ ] 03-06: Implement adaptive post-processing for Whisper vs Sherpa

### Phase 4: Advanced Features

**Goal**: Пользователь может настраивать качество и поведение транскрибации через UI

**Depends on**: Phase 3

**Requirements**: CFG-01, CFG-02, CFG-03, CFG-04, CFG-05

**Success Criteria** (what must be TRUE):
1. Quality profiles доступны в настройках (Fast/Balanced/Quality)
2. Пользователь может добавлять свои слова/термины в словарь коррекций
3. VAD настройки доступны в UI (threshold, min_silence_duration_ms)
4. Noise reduction настройки доступны в UI (enable/disable, intensity)
5. Выбор модели доступен в UI (tiny/base/small/medium/large-v3-turbo)

**Plans**: TBD (will be determined during planning)

Plans:
- [ ] 04-01: Implement quality profiles (Fast/Balanced/Quality)
- [ ] 04-02: Add user-defined correction dictionary
- [ ] 04-03: Add VAD settings to UI
- [ ] 04-04: Add noise reduction settings to UI
- [ ] 04-05: Add model selection to UI

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Critical Bug Fixes | 0/5 | Not started | - |
| 2. Noise Reduction + VAD | 0/5 | Not started | - |
| 3. Text Processing Enhancement | 0/6 | Not started | - |
| 4. Advanced Features | 0/5 | Not started | - |

**Total Progress:** [░░░░░░░░░░] 0% (0/21 plans)
