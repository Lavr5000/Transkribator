# Architecture

**Analysis Date:** 2026-01-27

## Pattern Overview

**Overall:** Client-Server Hybrid with Local Fallback

**Key Characteristics:**
- PyQt6-based GUI desktop application (local client)
- Optional remote transcription server with automatic fallback
- Multi-backend speech recognition architecture
- Threaded audio recording with callback-based processing
- Global hotkey/mouse button input handling
- Post-processing pipeline for text quality improvement

## Layers

**GUI Layer (`src/main_window.py`):**
- Purpose: User interface and interaction
- Location: `src/main_window.py`
- Contains: MainWindow, SettingsDialog, RecordButton, TextPopup, GradientWidget
- Depends on: PyQt6, audio recording, transcription, hotkeys, mouse handler
- Used by: Entry point (main.py)

**Audio Recording Layer (`src/audio_recorder.py`):**
- Purpose: Capture microphone audio with software gain
- Location: `src/audio_recorder.py`
- Contains: AudioRecorder class
- Depends on: sounddevice, soundfile, numpy
- Used by: MainWindow

**Transcription Layer (`src/transcriber.py`, `src/backends/`):**
- Purpose: Convert audio to text using multiple backends
- Location: `src/transcriber.py`, `src/backends/`
- Contains: Transcriber, BaseBackend, WhisperBackend, SherpaBackend, PodlodkaBackend
- Depends on: faster-whisper/openai-whisper, sherpa-onnx
- Used by: MainWindow

**Text Processing Layer (`src/text_processor.py`, `src/text_processor_enhanced.py`):**
- Purpose: Post-process transcribed text for accuracy
- Location: `src/text_processor.py`, `src/text_processor_enhanced.py`
- Contains: TextProcessor, AdvancedTextProcessor, EnhancedTextProcessor
- Depends on: deepmultilingualpunctuation (optional)
- Used by: Transcriber

**Input Handling Layer (`src/hotkeys.py`, `src/mouse_handler.py`):**
- Purpose: Global input control for recording
- Location: `src/hotkeys.py`, `src/mouse_handler.py`
- Contains: HotkeyManager, MouseButtonHandler
- Depends on: keyboard (preferred) or pynput
- Used by: MainWindow

**Remote Client Layer (`src/remote_client.py`):**
- Purpose: Optional remote transcription with local fallback
- Location: `src/remote_client.py`
- Contains: RemoteTranscriptionClient
- Depends on: requests
- Used by: MainWindow (via HybridTranscriptionThread)

**Server Layer (`TranscriberServer/`):**
- Purpose: Remote transcription service
- Location: `TranscriberServer/server.py`, `TranscriberServer/transcriber_wrapper.py`
- Contains: FastAPI app, RemoteTranscriber
- Depends on: fastapi, uvicorn, local transcription backends
- Used by: RemoteTranscriptionClient

## Data Flow

**Recording Transcription Flow:**

1. User triggers recording (hotkey/mouse/button)
2. HotkeyManager/MouseButtonHandler emits signal
3. MainWindow._toggle_recording() → _start()
4. AudioRecorder.start() begins capturing audio via sounddevice callback
5. Audio chunks collected in queue by _collect_audio() thread
6. User stops recording (hotkey/mouse/button)
7. AudioRecorder.stop() concatenates chunks, applies mic_boost, returns numpy array
8. HybridTranscriptionThread started:
   - Tries RemoteTranscriptionClient.transcribe_remote()
   - On failure, falls back to Transcriber.transcribe()
9. Backend transcribes audio:
   - WhisperBackend: faster-whisper with VAD
   - SherpaBackend: sherpa-onnx with GigaAM models
10. Text post-processing (if enabled):
    - TextProcessor or EnhancedTextProcessor
    - Error corrections, punctuation restoration
11. MainWindow._done() receives result
12. Auto-copy to clipboard (pyperclip)
13. Auto-paste via safe_paste_text() or type_text()
14. HistoryManager.add_entry() saves transcription

**State Management:**
- Recording state: `_recording` flag
- Processing lock: `_processing` flag prevents concurrent operations
- Debounce: `_last_toggle_time` prevents rapid re-activation
- Thread-safe signals: Qt signals for cross-thread communication

## Key Abstractions

**BaseBackend (`src/backends/base.py`):**
- Purpose: Abstract interface for speech recognition backends
- Examples: `src/backends/whisper_backend.py`, `src/backends/sherpa_backend.py`
- Pattern: Abstract base class with load_model(), unload_model(), transcribe(), is_model_loaded()

**Transcriber (`src/transcriber.py`):**
- Purpose: Unified interface for multi-backend transcription
- Examples: Instantiated in MainWindow.__init__()
- Pattern: Facade over backend selection + text post-processing

**TextProcessor (`src/text_processor.py`):**
- Purpose: Correction rules and text normalization
- Examples: Russian phonetic substitutions, punctuation fixes
- Pattern: Dictionary-based substitutions + regex pattern corrections

## Entry Points

**Local Application:**
- Location: `main.py`
- Triggers: Direct execution
- Responsibilities: Dependency check, import src.main_window, run Qt app

**Remote Server:**
- Location: `TranscriberServer/server.py`
- Triggers: uvicorn server startup
- Responsibilities: FastAPI endpoints for /transcribe, /status, /result, /health

## Error Handling

**Strategy:** Graceful degradation with fallback

**Patterns:**
- Remote transcription failure → automatic local fallback (HybridTranscriptionThread)
- Backend not available → ImportError handling with message
- Model file missing → FileNotFoundError with download instructions
- Recording too short (< 0.5s) → Silent discard, reset UI

**Cross-Cutting Concerns:**

**Logging:** Minimal stdout/stderr printing, debug.log file for troubleshooting

**Validation:** Audio duration check, device availability check, health check for remote

**Authentication:** None (local-only, or open HTTP endpoints for remote server)

---

*Architecture analysis: 2026-01-27*
