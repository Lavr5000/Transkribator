# Codebase Components

**Analysis Date:** 2026-01-27

## Directory Layout

```
Transkribator/
├── main.py              # Entry point for local application
├── pyproject.toml       # Package configuration
├── requirements.txt     # CPU dependencies
├── src/                 # Core application source
│   ├── __init__.py
│   ├── main_window.py    # PyQt6 GUI (550+ lines, MainWindow)
│   ├── config.py         # Configuration dataclass
│   ├── audio_recorder.py # Audio capture with software gain
│   ├── transcriber.py    # Transcription facade
│   ├── text_processor.py # Basic text corrections
│   ├── text_processor_enhanced.py # + punctuation restoration
│   ├── hotkeys.py        # Global hotkey handling
│   ├── mouse_handler.py  # Mouse button recording control
│   ├── history_manager.py # Transcription history storage
│   ├── remote_client.py  # Remote transcription client
│   └── backends/         # Speech recognition backends
│       ├── __init__.py
│       ├── base.py       # BaseBackend abstract class
│       ├── whisper_backend.py  # OpenAI Whisper (faster-whisper)
│       ├── sherpa_backend.py   # Sherpa-ONNX GigaAM
│       └── podlodka_turbo_backend.py  # Whisper-Podlodka-Turbo
├── TranscriberServer/    # Remote transcription server
│   ├── server.py         # FastAPI application
│   └── transcriber_wrapper.py  # RemoteTranscriber class
├── TranscriberClient/    # Standalone remote client (unused)
├── RemotePackage/        # Packaged version for remote deployment
├── models/               # Downloaded model files
│   └── sherpa/           # Sherpa-ONNX models
├── scripts/              # Installation and utility scripts
└── venv/                 # Virtual environment (not in repo)
```

## Directory Purposes

**`src/`:** Core application source code
- Purpose: Main client application implementation
- Contains: All Qt GUI, audio handling, transcription logic
- Key files: `main_window.py` (550+ lines), `transcriber.py`, `audio_recorder.py`

**`src/backends/`:** Speech recognition implementations
- Purpose: Pluggable backend architecture for different STT engines
- Contains: Abstract base + concrete implementations
- Key files: `base.py`, `whisper_backend.py`, `sherpa_backend.py`

**`TranscriberServer/`:** Remote transcription service
- Purpose: Optional server for remote transcription
- Contains: FastAPI app, background task handling
- Key files: `server.py`, `transcriber_wrapper.py`

**`RemotePackage/`:** Packaged deployment version
- Purpose: Standalone package for remote deployment
- Contains: Copy of src/, server components
- Generated: Yes, for distribution

**`models/`:** Model storage
- Purpose: Downloaded speech recognition models
- Contains: Sherpa-ONNX model files (model.onnx, tokens.txt, config.json)
- Generated: Yes, models downloaded at runtime

**`scripts/`:** Installation and setup
- Purpose: Automated installation and model downloading
- Contains: Shell/batch scripts for setup
- Key files: `download_models.py`

## Key File Locations

**Entry Points:**
- `main.py`: Local application entry point
- `TranscriberServer/server.py`: Remote server entry point

**Configuration:**
- `src/config.py`: Config dataclass with defaults, load/save methods
- Config location: `~/.config/WhisperTyping/WhisperTyping/config.json` (platformdirs)

**Core Logic:**
- `src/audio_recorder.py`: AudioRecorder class (sounddevice-based)
- `src/transcriber.py`: Transcriber class (backend facade)
- `src/text_processor.py`: TextProcessor, AdvancedTextProcessor
- `src/text_processor_enhanced.py`: EnhancedTextProcessor (with punctuation)

**Backends:**
- `src/backends/whisper_backend.py`: WhisperBackend (faster-whisper preferred)
- `src/backends/sherpa_backend.py`: SherpaBackend (GigaAM models)
- `src/backends/podlodka_turbo_backend.py`: PodlodkaTurboBackend (Russian-fine-tuned)

**Input Handling:**
- `src/hotkeys.py`: HotkeyManager (keyboard lib preferred, pynput fallback)
- `src/mouse_handler.py`: MouseButtonHandler (pynput)

**Remote:**
- `src/remote_client.py`: RemoteTranscriptionClient (with fallback)

**Testing:**
- `test_*.py` files in root: Various test scripts (not in src/)

## Naming Conventions

**Files:**
- Modules: `lowercase_with_underscores.py` (e.g., `audio_recorder.py`)
- Classes: `CamelCase` (e.g., `AudioRecorder`, `MainWindow`)
- Functions: `lowercase_with_underscores` (e.g., `transcribe_remote`, `load_model`)

**Directories:**
- Source: `lowercase` (e.g., `src/`, `backends/`)
- Server: `CamelCase` (e.g., `TranscriberServer/`)

**Constants:**
- Global: `UPPER_CASE` (e.g., `AUDIO_AVAILABLE`, `HOTKEY_BACKEND`)
- Class attributes: `_private` (e.g., `_model`, `_lock`)

## Where to Add New Code

**New Backend:**
- Implementation: `src/backends/{name}_backend.py`
- Inherit from: `BaseBackend` in `src/backends/base.py`
- Register in: `src/backends/__init__.py` (get_backend function)
- Update: `src/config.py` BACKENDS, MODELS dictionaries

**New Text Processor:**
- Implementation: `src/text_processor_{name}.py`
- Import in: `src/transcriber.py` (conditional import pattern)

**New Feature (GUI):**
- Implementation: `src/main_window.py` (if UI-related)
- Or new module: `src/{feature}.py`
- Import in: `src/main_window.py`

**Utilities:**
- Shared helpers: `src/utils.py` (create if needed)
- Or existing: `src/hotkeys.py` (for keyboard utilities)

## Special Directories

**`venv/`:**
- Purpose: Python virtual environment
- Generated: Yes
- Committed: No (in .gitignore)

**`models/sherpa/`:**
- Purpose: Sherpa-ONNX model storage
- Generated: Yes (downloaded at runtime or via scripts)
- Committed: No (too large for git)

**`.planning/`:**
- Purpose: Project planning and codebase documentation
- Generated: Yes
- Committed: Yes

---

*Component analysis: 2026-01-27*
