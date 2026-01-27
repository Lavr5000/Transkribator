---
phase: 01-critical-bug-fixes
plan: 02
subsystem: speech-recognition
tags: [sherpa-onnx, transducer, gigaam, russian-asr, onnx, bug-fix]

# Dependency graph
requires:
  - phase: 01-01
    provides: project initialization and testing infrastructure
provides:
  - Fixed Sherpa backend using correct Transducer architecture (NOT CTC)
  - Updated model configurations for encoder/decoder/joiner files
  - Optimal accuracy settings with max_active_paths=4
affects: [01-03, 01-04, 02-accuracy-testing, 03-performance-benchmarking]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Transducer model architecture for RNN-T speech recognition
    - Encoder/Decoder/Joiner file structure for ONNX models
    - max_active_paths parameter for beam search optimization

key-files:
  created: []
  modified:
    - src/backends/sherpa_backend.py
    - RemotePackage/src/backends/sherpa_backend.py

key-decisions:
  - "Use from_nemo_transducer() instead of from_nemo_ctc() - GigaAM v2 is RNN-T architecture"
  - "Set max_active_paths=4 for optimal balance of speed vs accuracy for Russian language"
  - "Check for encoder.int8.onnx as primary, fallback to encoder.onnx"

patterns-established:
  - "Transducer model loading: encoder + decoder + joiner + tokens"
  - "Model file validation: check all three components before loading"

# Metrics
duration: 5min
completed: 2026-01-27
---

# Phase 01-02: Sherpa Backend Architecture Fix Summary

**Migration from CTC to Transducer architecture for GigaAM v2 Russian ASR with encoder/decoder/joiner model files and max_active_paths=4 optimization**

## Performance

- **Duration:** 5 min
- **Started:** 2026-01-27T12:17:48Z
- **Completed:** 2026-01-27T12:22:48Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- Fixed critical architecture bug: Sherpa backend was using CTC mode for Transducer model
- Updated model URLs to point to correct Transducer models (sherpa-onnx-nemo-transducer-giga-am)
- Replaced from_nemo_ctc() with from_nemo_transducer() factory method
- Added encoder/decoder/joiner file detection and loading
- Set max_active_paths=4 for optimal Russian transcription accuracy
- Synchronized changes across local and RemotePackage versions

## Task Commits

1. **Task 1: Fix Sherpa backend: CTC to Transducer architecture** - `c135d9b` (fix)

**Plan metadata:** (pending)

## Files Created/Modified
- `src/backends/sherpa_backend.py` - Migrated from CTC to Transducer architecture
  - Updated MODELS dictionary with Transducer model files
  - Changed _check_model_files() to validate encoder/decoder/joiner
  - Replaced load_model() to use from_nemo_transducer() with max_active_paths=4
- `RemotePackage/src/backends/sherpa_backend.py` - Same changes synchronized

## Decisions Made
- Use from_nemo_transducer() because GigaAM v2 is an RNN-T (Transducer) model, NOT CTC
- Set max_active_paths=4 based on research recommendations for optimal Russian accuracy
- Check for encoder.int8.onnx first (quantized version), fallback to encoder.onnx
- Update both local and RemotePackage versions to maintain synchronization

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all changes applied successfully without errors.

## User Setup Required

None - code changes only. No external service configuration required.

## Next Phase Readiness
- Sherpa backend now uses correct Transducer architecture
- Ready for accuracy testing to measure quality improvement
- Model files need to be downloaded from new Transducer URLs before first use
- Expect significant accuracy improvement (from "торопинка или сок" to "тропинка лесок")

---
*Phase: 01-critical-bug-fixes*
*Plan: 01-02*
*Completed: 2026-01-27*
