# Roadmap: Transkribator

## Milestones

- ✅ **v1.0 Audio Quality** - Phases 1-4 (shipped 2026-01-29)
- 🚧 **v1.1 Remote Server Optimization** - Phases 5-8 (in progress)
- 📋 **v1.2 Realtime Streaming** - Phases 9+ (planned)

## Phases

<details>
<summary>✅ v1.0 Audio Quality (Phases 1-4) - SHIPPED 2026-01-29</summary>

### Phase 1: Critical Bug Fixes
**Goal**: Модели Whisper и Sherpa используют правильные параметры и архитектуру
**Plans**: 5 plans

Plans:
- [x] 01-01: Fix Whisper backend parameters (language="ru", beam_size=5)
- [x] 01-02: Fix Sherpa backend architecture (CTC → Transducer)
- [x] 01-03: Synchronize improvements between client and server
- [x] 01-04: Implement testing framework
- [x] 01-05: Verify Phase 1 goal achievement

**Status**: COMPLETE (2026-01-27) — All 16 requirements verified PASSED

### Phase 2: Noise Reduction + VAD
**Goal**: Аудио на входе очищено от шума, тишина удалена до транскрибации
**Plans**: 5 plans

Plans:
- [x] 02-01: Integrate WebRTC Noise/Gain into AudioRecorder
- [x] 02-02: Replace 20x software gain with adaptive AGC
- [x] 02-03: Integrate Silero VAD into SherpaBackend
- [x] 02-04: Implement VAD for all backends
- [x] 02-05: Add VAD visualization in UI

**Status**: COMPLETE (2026-01-27) — All 9 requirements verified PASSED

### Phase 3: Text Processing Enhancement
**Goal**: Пост-обработка текста исправляет 100+ типичных ошибок русской речи
**Plans**: 6 plans

Plans:
- [x] 03-01: Expand EnhancedTextProcessor from 50 to 100+ correction rules
- [x] 03-02: Add phonetic corrections for Russian language
- [x] 03-03: Add morphological corrections using pymorphy2
- [x] 03-04: Create proper noun dictionary (779 entries)
- [x] 03-05: Improve capitalization after punctuation
- [x] 03-06: Implement adaptive post-processing with punctuation restoration

**Status**: COMPLETE (2026-01-29) — All 7 requirements verified PASSED

### Phase 4: Advanced Features
**Goal**: Пользователь может настраивать качество и поведение транскрибации
**Plans**: 5 plans

Plans:
- [x] 04-01: Implement quality profiles (Fast/Balanced/Quality)
- [x] 04-02: Add user-defined correction dictionary
- [x] 04-03: Add VAD settings to UI
- [x] 04-04: Add noise reduction settings to UI
- [x] 04-05: Add enhanced model selection with metadata

**Status**: COMPLETE (2026-01-29) — All 5 requirements verified PASSED

</details>

### 🚧 v1.1 Remote Server Optimization (In Progress)

**Milestone Goal:** Стабильная быстрая работа удалённого сервера транскрибации

#### Phase 5: Server Configuration
**Goal**: Сервер использует оптимизированные параметры транскрибации
**Depends on**: Phase 4
**Requirements**: SRV-01, SRV-02, SRV-03, SRV-04, SRV-05
**Success Criteria** (what must be TRUE):
  1. Сервер транскрибирует с forced language="ru" (не auto)
  2. Сервер использует sherpa/giga-am-v2-ru бэкенд (10x быстрее)
  3. Сервер применяет VAD для удаления тишины из аудио
  4. Сервер использует параметры quality profile (threshold, silence durations)
  5. Сервер применяет пост-обработку текста (251 правило коррекции)
**Plans**: 2 plans

Plans:
- [ ] 05-01: Update transcriber_wrapper.py with optimized parameters
- [ ] 05-02: Integrate text post-processing on server side

#### Phase 6: Audio Compression
**Goal**: Быстрая передача аудио за счёт Opus сжатия
**Depends on**: Phase 5
**Requirements**: AUDIO-01, AUDIO-02, AUDIO-03, AUDIO-04
**Success Criteria** (what must be TRUE):
  1. Клиент кодирует аудио в Opus перед отправкой на сервер
  2. Сервер декодирует Opus и обрабатывает аудио
  3. WAV fallback работает для совместимости со старыми версиями
  4. Размер файла для 30 секунд записи < 100 KB (было ~960 KB)
**Plans**: 2 plans

Plans:
- [ ] 06-01: Implement Opus encoding in client
- [ ] 06-02: Implement Opus decoding on server

#### Phase 7: Client Optimization
**Goal**: Быстрый отклик и видимость процесса транскрибации
**Depends on**: Phase 6
**Requirements**: CLIENT-01, CLIENT-02, CLIENT-03, CLIENT-04
**Success Criteria** (what must be TRUE):
  1. VAD на клиенте отрезает тишину ДО отправки на сервер
  2. Polling interval уменьшен до 0.5 сек (быстрая реакция)
  3. Логи показывают время каждого этапа (upload, transcription, download)
  4. Логи показывают размер файла и скорость передачи
**Plans**: 2 plans

Plans:
- [ ] 07-01: Implement client-side VAD and reduce polling interval
- [ ] 07-02: Add detailed timing and size logging

#### Phase 8: Network Stability
**Goal**: Надёжное подключение к удалённому серверу
**Depends on**: Phase 7
**Requirements**: NET-01, NET-02, NET-03, NET-04, NET-05
**Success Criteria** (what must be TRUE):
  1. Сервер автоматически запускается при старте системы
  2. Serveo туннель автоматически восстанавливается при обрыве
  3. Health check endpoint корректно отвечает на запросы
  4. Логи сервера доступны для диагностики проблем
  5. Fallback на локальную транскрибацию при недоступности сервера
**Plans**: 2 plans

Plans:
- [ ] 08-01: Implement server autostart and tunnel recovery
- [ ] 08-02: Implement health check and fallback mechanism

## Progress

**Execution Order:**
Phases execute in numeric order: 5 → 6 → 7 → 8

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Critical Bug Fixes | v1.0 | 5/5 | Complete | 2026-01-27 |
| 2. Noise Reduction + VAD | v1.0 | 5/5 | Complete | 2026-01-27 |
| 3. Text Processing Enhancement | v1.0 | 6/6 | Complete | 2026-01-29 |
| 4. Advanced Features | v1.0 | 5/5 | Complete | 2026-01-29 |
| 5. Server Configuration | v1.1 | 0/2 | Not started | - |
| 6. Audio Compression | v1.1 | 0/2 | Not started | - |
| 7. Client Optimization | v1.1 | 0/2 | Not started | - |
| 8. Network Stability | v1.1 | 0/2 | Not started | - |

**Overall Progress:** [████████░░░░░░░░░░] 50% (21/21 plans complete in v1.0, 0/8 in v1.1)
