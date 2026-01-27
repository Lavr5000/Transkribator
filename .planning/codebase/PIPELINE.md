# Audio Processing Pipeline

**Analysis Date:** 2026-01-27

## Pipeline Overview

**Type:** Real-time audio capture with batch transcription

**Stages:**
1. Input Trigger → 2. Audio Capture → 3. Software Gain → 4. Transcription → 5. Post-Processing → 6. Output

## Stage 1: Input Trigger

**Entry Points:**
- Global hotkey: `Ctrl+Shift+Space` (configurable via `config.hotkey`)
- Mouse button: Middle click (configurable via `config.mouse_button`)
- GUI button: RecordButton in MainWindow

**Implementation:**
- `src/hotkeys.py`: HotkeyManager using keyboard library (preferred) or pynput
- `src/mouse_handler.py`: MouseButtonHandler using pynput
- Thread-safe: Uses Qt signals (`_request_toggle`) for main thread execution

**Debounce Protection:**
- 300ms debounce on start only (not on stop)
- `_last_toggle_time` tracking in MainWindow
- `_processing` flag prevents concurrent operations

## Stage 2: Audio Capture

**Component:** `AudioRecorder` in `src/audio_recorder.py`

**Flow:**
```
AudioRecorder.start()
  ├── sounddevice.InputStream creation (samplerate=16000, channels=1, dtype=float32)
  ├── _audio_callback() called periodically by sounddevice
  │   ├── Copy indata (audio chunk)
  │   └── Put in _audio_queue (thread-safe queue)
  └── _collect_audio() thread running
      ├── Get chunks from _audio_queue
      └── Append to _audio_data list
```

**Parameters:**
- Sample rate: 16000 Hz (configurable via `config.sample_rate`)
- Channels: 1 (mono)
- Block size: 1024 frames
- Device: System default or specific index (config.audio_device)

**Visualization:**
- `on_level_update` callback provides audio level for UI
- Level calculated as `np.abs(data).mean()`

## Stage 3: Software Gain

**Component:** `AudioRecorder.stop()`

**Implementation:**
```python
# Apply software boost if needed
if self.mic_boost != 1.0:
    audio = audio * self.mic_boost
    # Clip to prevent distortion
    audio = np.clip(audio, -1.0, 1.0)
```

**Configuration:**
- Setting: `config.mic_boost` (default: 20.0)
- Range: Any positive float (1.0 = no boost)
- Purpose: Increase quiet microphone input digitally

**Processing:**
- Applied after recording stops, before transcription
- Simple multiplication followed by hard clipping to [-1.0, 1.0]
- No dynamic range compression or normalization

## Stage 4: Transcription

**Component:** `Transcriber` with backend selection

**Backend Options:**

**1. WhisperBackend (`src/backends/whisper_backend.py`)**
- Primary: faster-whisper (faster, C++-optimized)
- Fallback: openai-whisper
- Models: tiny, base, small, medium, large, large-v3
- VAD: Enabled (vad_filter=True, min_silence_duration_ms=200)
- Device: Auto-detects CUDA, falls back to CPU
- Output: Includes punctuation (Whisper native)

**2. SherpaBackend (`src/backends/sherpa_backend.py`)**
- Engine: sherpa-onnx (ONNX Runtime)
- Models: giga-am-v2-ru, giga-am-ru (Russian-optimized)
- Device: CPU only (ONNX limitation)
- Threads: Auto-detected CPU count, max 8
- Output: No punctuation (CTC model limitation)
- Use EnhancedTextProcessor for punctuation restoration

**3. PodlodkaTurboBackend**
- Engine: Whisper-based fine-tuned for Russian
- Status: Referenced but implementation details in podlodka_turbo_backend.py

**Transcription Flow:**
```
Transcriber.transcribe(audio, sample_rate)
  ├── Backend.transcribe(audio, sample_rate)
  │   ├── Ensure float32, mono
  │   ├── Resample to 16kHz if needed (librosa or scipy)
  │   └── Run inference (Whisper or Sherpa-ONNX)
  └── Return (text, duration)
```

**Resampling:**
- Preferred: librosa.resample() (faster)
- Fallback: scipy.signal.resample() (slower)
- Target: 16000 Hz for all backends

## Stage 5: Post-Processing

**Component:** TextProcessor / EnhancedTextProcessor

**For Whisper Backend:**
- Uses: `AdvancedTextProcessor`
- Includes: Punctuation from Whisper (native)
- Applies: Error corrections only

**For Sherpa Backend:**
- Uses: `EnhancedTextProcessor` (if available)
- Includes: Punctuation restoration (deepmultilingualpunctuation)
- Applies: Error corrections + punctuation + capitalization

**Processing Steps:**
1. Fix common transcription errors (dictionary-based)
2. Restore punctuation (Sherpa only, using ML model)
3. Fix punctuation placement (regex patterns)
4. Fix capitalization (sentence start, after punctuation)
5. Final cleanup (extra spaces, trailing punctuation)

**Error Corrections (Russian):**
- Phonetic substitutions: "лыбки" → "улыбки"
- Verb forms: "станек" → "станет"
- Prepositions: "растебе" → "к тебе"
- Double letters: "в в" → "в"

**Configuration:**
- Setting: `config.enable_post_processing` (default: True)
- Toggle: Available in Settings dialog

## Stage 6: Output

**Auto-Copy:**
- Implementation: pyperclip.copy(text)
- Setting: `config.auto_copy` (default: True)
- Timing: After transcription completes

**Auto-Paste:**
- Method 1 (Recommended): `safe_paste_text()`
  - Copy to clipboard first
  - Simulate Ctrl+Shift+V (terminal paste)
  - Configurable delay via `config.paste_delay`
- Method 2 (Legacy): `type_text()`
  - Character-by-character simulation
  - Can crash terminal apps
  - Not recommended

**Text Popup:**
- Component: `TextPopup` widget
- Behavior: Shows above main window for 5 seconds
- Features: Copy button, auto-hide
- Always triggered after transcription

**History:**
- Component: `HistoryManager`
- Storage: `~/.config/WhisperTyping/WhisperTyping/history.json`
- Max entries: 50 (configurable)
- Fields: text, timestamp, duration, backend, model, word_count

## Remote Transcription (Optional)

**HybridTranscriptionThread:**
```
Try RemoteTranscriptionClient.transcribe_remote()
  ├── Check server health (cached, 30s TTL)
  ├── Upload WAV to remote server
  ├── Poll status endpoint
  └── Download result
If successful:
  └── Return text with is_remote=True
If failed:
  └── Fallback to local Transcriber.transcribe()
      └── Return text with is_remote=False
```

**Server Endpoints:**
- `POST /transcribe`: Upload audio file
- `GET /status/{task_id}`: Check transcription status
- `GET /result/{task_id}`: Download result
- `GET /health`: Health check

**Server Locations:**
- Primary: Tailscale VPN (100.102.178.110:8000)
- Backup: serveo.net tunnel

## VAD (Voice Activity Detection) Status

**Whisper Backend:**
- VAD: Enabled via `vad_filter=True`
- Configuration: `vad_parameters=dict(min_silence_duration_ms=200)`
- Purpose: Faster transcription by skipping silence

**Sherpa Backend:**
- VAD: Not implemented (CTC model processes full audio)
- Workaround: Post-processing silence removal not implemented

**AudioRecorder:**
- VAD: Not implemented (records continuously)
- Future: Could implement before transcription to reduce audio size

## Audio Enhancement Settings

**Current Implementations:**
- Software gain: `config.mic_boost` (simple multiplier)
- Clipping: Hard clip to [-1.0, 1.0] after gain

**NOT Implemented:**
- Noise reduction
- Dynamic range compression
- Automatic gain control (AGC)
- High-pass filtering
- Normalization (RMS/LUFS)

---

*Pipeline analysis: 2026-01-27*
