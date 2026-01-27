---
phase: 02-noise-reduction-vad
plan: 04
subsystem: audio-processing
tags: [vad, silero, sherpa-onnx, whisper, podlodka, noise-reduction]

# Dependency graph
requires:
  - phase: 02-03
    provides: Silero VAD integration pattern in SherpaBackend
provides:
  - Unified VAD configuration across all transcription backends
  - VAD parameters configurable via config.py
  - Consistent silence filtering behavior across Whisper, Sherpa, and Podlodka backends
affects: [Phase 3 - Post-processing, Phase 4 - Testing]

# Tech tracking
tech-stack:
  added: []
  patterns: [unified VAD parameter passing, auto-download of VAD models from HuggingFace]

key-files:
  created: []
  modified: [src/backends/whisper_backend.py, src/backends/podlodka_turbo_backend.py, src/backends/sherpa_backend.py, src/transcriber.py, src/main_window.py, RemotePackage/src/backends/whisper_backend.py, RemotePackage/src/backends/podlodka_turbo_backend.py, RemotePackage/src/backends/sherpa_backend.py, RemotePackage/src/transcriber.py]

key-decisions:
  - "VAD parameters unified across all backends (vad_enabled, vad_threshold, min_silence_duration_ms, min_speech_duration_ms)"
  - "Silero VAD model shared via single models/sherpa/silero-vad directory"
  - "Graceful fallback if VAD fails - transcription continues without VAD"

patterns-established:
  - "Pattern: VAD initialization in load_model() after model loading"
  - "Pattern: VAD filtering at start of transcribe() before main processing"
  - "Pattern: Client-server synchronization - all changes applied to both src/ and RemotePackage/"

# Metrics
duration: 8min
completed: 2026-01-27
---

# Phase 02-04: VAD for All Backends Summary

**Silero VAD integration extended to WhisperBackend and PodlodkaBackend with unified configuration from config.py**

## Performance

- **Duration:** 8 min
- **Started:** 2026-01-27T18:45:00Z
- **Completed:** 2026-01-27T18:53:00Z
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments

- WhisperBackend now uses Silero VAD for silence detection before transcription
- PodlodkaBackend now uses Silero VAD for silence detection before transcription
- SherpaBackend updated to accept VAD parameters from config (previously hardcoded)
- Transcriber passes VAD configuration from config.py to all backends
- All backends use identical VAD pattern and shared model directory

## Task Commits

Each task was committed atomically:

1. **Task 1: Add VAD to WhisperBackend** - `7e90fb7` (feat)
2. **Task 2: Add VAD to PodlodkaBackend** - `e164f4a` (feat)
3. **Task 3: Wire VAD config from Transcriber to backends** - `9cf95b9` (feat)

**Plan metadata:** (to be added)

## Files Created/Modified

- `src/backends/whisper_backend.py` - Added Silero VAD integration with _get_vad_model_dir() and VAD filtering
- `src/backends/podlodka_turbo_backend.py` - Added Silero VAD integration with _get_vad_model_dir() and VAD filtering
- `src/backends/sherpa_backend.py` - Updated __init__ to accept VAD parameters instead of hardcoded values
- `src/transcriber.py` - Added VAD parameters to __init__ and _create_backend()
- `src/main_window.py` - Updated to pass VAD config from config.py to Transcriber
- `RemotePackage/src/backends/whisper_backend.py` - Synchronized with src/ version
- `RemotePackage/src/backends/podlodka_turbo_backend.py` - Synchronized with src/ version
- `RemotePackage/src/backends/sherpa_backend.py` - Synchronized with src/ version
- `RemotePackage/src/transcriber.py` - Synchronized with src/ version

## Decisions Made

- VAD parameters default to disabled (vad_enabled=False) in backends, must be explicitly enabled via config
- VAD model auto-downloads from HuggingFace if missing (csukuangfj/sherpa-onnx-silero-vad)
- Shared model directory: models/sherpa/silero-vad (used by all backends)
- Graceful degradation: if VAD fails, transcription continues with original audio

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all changes applied successfully.

## User Setup Required

None - VAD model auto-downloads on first use if enabled in config.

## Next Phase Readiness

- All three backends (Whisper, Sherpa, Podlodka) now have consistent VAD behavior
- VAD can be toggled via config.vad_enabled in config.py
- Phase 02-05 (VAD UI Controls) can now add UI elements to configure VAD parameters
- No blockers identified

---
*Phase: 02-noise-reduction-vad*
*Completed: 2026-01-27*
