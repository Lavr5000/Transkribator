# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-01-27)

**Core value:** Точность распознавания русской речи на уровне WhisperTyping без существенной потери скорости
**Current focus:** Phase 2: Noise Reduction + VAD

## Current Position

Phase: 2 of 4 (Noise Reduction + VAD)
Plan: 4 of 5 in current phase
Status: In progress
Last activity: 2026-01-27 — Completed 02-02: WebRTC AGC Migration

Progress: [███████░░░░░░░░░░░░░░░░░░░░] 80%

## Performance Metrics

**Velocity:**
- Total plans completed: 8
- Average duration: 4.0 min
- Total execution time: 0.53 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 5/5 | 21 min | 4.2 min |
| 2 | 3/5 | 11 min | 3.7 min |
| 3 | 0/6 | - | - |
| 4 | 0/5 | - | - |

**Recent Trend:**
- Last 5 plans: 3 min (WebRTC NS), 4 min (AGC), 4 min (VAD), 3 min, 5 min
- Trend: Stable (fast execution)

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Initialization]: Приоритет русского языка confirmed (пользователь использует для русского)
- [Initialization]: Баланс скорости и качества — пользователь выбрал "Баланс" (beam_size=2)
- [Initialization]: VAD для всех бэкендов — Sherpa сейчас без VAD, страдает качество
- [Initialization]: Enhanced post-processing — WhisperTyping использует успешно
- [01-01]: Whisper beam_size=5 chosen for quality mode (+15-30% accuracy, +30% processing time acceptable)
- [01-01]: Temperature=0.0 for deterministic decoding (prevents hallucinations)
- [01-01]: VAD parameters optimized for Russian (300ms silence, 400ms speech_pad)
- [01-02]: Use from_nemo_transducer() instead of from_nemo_ctc() — GigaAM v2 is RNN-T architecture
- [01-02]: Set max_active_paths=4 for optimal Russian accuracy based on research recommendations
- [01-02]: Check for encoder.int8.onnx first (quantized), fallback to encoder.onnx
- [01-03]: Atomic synchronization pattern established — backend changes must be applied to both src/ and RemotePackage/src/ simultaneously
- [01-03]: Client-server parameter consistency verified — both directories produce identical results
- [01-04]: Pure Python Levenshtein implementation chosen for quality metrics (no external ML dependencies)
- [01-04]: Character Error Rate (CER) prioritized over WER for morphological languages like Russian
- [01-04]: Direct execution model for tests — can run standalone without pytest requirement
- [01-05]: All 16 Phase 1 requirements verified via automated code inspection (grep + diff)
- [01-05]: Whisper backend confirmed: language='ru' (line 32, 159), beam_size=5 (line 165), temperature=0.0 (line 166)
- [01-05]: Sherpa backend confirmed: Transducer mode (line 168), max_active_paths=4 (line 175)
- [01-05]: Client-server synchronization confirmed: src/ and RemotePackage/ identical (diff empty)
- [01-05]: Expected impact documented: 15-30% accuracy improvement, primary gain from Sherpa Transducer fix (+20-30%)
- [02-01]: WebRTC noise suppression integrated with 10ms chunk processing (160 samples @ 16kHz)
- [02-01]: Noise suppression level 2 (moderate) chosen as default - balances quality vs overhead
- [02-01]: Fallback pattern established for optional platform dependencies (try/except on import)
- [02-02]: AGC target level set to -3 dBFS for optimal headroom without clipping
- [02-02]: Initial gain adjustment set to 10 dB for quiet microphone boost
- [02-02]: AGC uses RMS-based level detection with 100ms attack time
- [02-02]: mic_boost deprecated (default changed from 20.0 to 1.0)
- [02-02]: Software boost only applies when webrtc_enabled=False (prevents double-boosting)
- [02-03]: Silero VAD integrated via sherpa_onnx.OfflineVad for speech detection
- [02-03]: VAD threshold=0.5, min_silence=800ms, min_speech=500ms for Russian speech patterns
- [02-03]: VAD model auto-downloads from HuggingFace (csukuangfj/sherpa-onnx-silero-vad)
- [02-03]: Graceful fallback if VAD fails - transcription continues without VAD

### Pending Todos

None yet.

### Blockers/Concerns

**Phase 1 Status:**
- ✅ COMPLETE - All 16 requirements verified (MODEL-01 to MODEL-08, TEST-01 to TEST-05, SRV-01 to SRV-03)
- ⚠️ RECOMMENDED: Run A/B test to measure actual WER/CER improvement: `python tests/test_backend_quality.py`
- 📊 Expected: 15-30% accuracy improvement based on research (Sherpa Transducer fix is primary driver)

**Phase 2 Concerns:**

**Phase 2 Concerns:**
- Punctuation model accuracy for Russian — deepmultilingualpunctuation not trained on Russian, may need to fallback to rule-based

**Phase 3 Concerns:**
- Сбор реальных error patterns — нужен A/B тест для измерения CER улучшения

## Session Continuity

Last session: 2026-01-27 18:32 UTC
Stopped at: Completed 02-02 (WebRTC AGC Migration)
Resume file: None

---

**Next Step:** Phase 02-04: VAD for Whisper backend - apply same VAD pattern to WhisperBackend
