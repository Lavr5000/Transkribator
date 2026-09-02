"""Configuration management for WhisperTyping."""
import json
import os
import time
import threading
from dataclasses import dataclass, field, fields, asdict
from pathlib import Path
from typing import Optional
import logging

import platformdirs

logger = logging.getLogger("transkribator")

# Bumped whenever stored config.json needs a migration (see Config.migrate).
# 1 -> 2 (2.4.0): single backend, no cloud/remote/Telegram fields, devices
# stored by host API + name instead of a PortAudio index.
CONFIG_VERSION = 2


@dataclass
class Config:
    """Application configuration."""

    # Quality profile (presets for Fast/Balanced/Quality)
    quality_profile: str = "quality"  # fast, balanced, quality (default: quality for max accuracy)

    # User-defined correction dictionary
    user_dictionary: list = field(default_factory=list)  # [{"wrong": str, "correct": str, "case_sensitive": bool}]

    # Backend selection
    backend: str = "sherpa"  # the only engine since 2.4.0 — local Sherpa-ONNX

    # Model settings
    model_size: str = "giga-am-v3-ru-punct"   # giga-am-v3-ru-punct (default, shipped in the release;
                                              # ASR emits punctuation itself, so the 560M XLM-R restorer
                                              # never loads — no network needed at runtime),
                                              # giga-am-v3-ru, giga-am-v2-ru, giga-am-ru
    language: str = "ru"  # auto-detect or specific language code
    device: str = "auto"  # auto, cpu, cuda
    compute_type: str = "auto"  # auto, int8, float16, float32
    enable_post_processing: bool = True  # Enable text post-processing for better accuracy

    # Schema version of the stored config.json (see Config.migrate)
    config_version: int = CONFIG_VERSION

    # Audio settings
    sample_rate: int = 16000
    channels: int = 1
    # Devices are stored by host API + name, not by PortAudio index: indexes
    # move across reboots, USB re-plugs and driver updates. The legacy index
    # from <= 2.3 configs is resolved once and written back as a name.
    audio_device_name: str = ""      # "" = system default input
    audio_hostapi: str = ""          # e.g. "windows wasapi", "mme"
    audio_device_legacy_index: int = -1
    mic_boost: float = 1.0  # Software gain multiplier (DEPRECATED: Use WebRTC AGC instead)
                                # Only used when webrtc_enabled=False
                                # 1.0 = no boost, kept for fallback compatibility

    # WebRTC audio processing settings
    webrtc_enabled: bool = True  # Enable WebRTC noise suppression and AGC
    noise_suppression_level: int = 2  # 0-4: 0=off, 1=low, 2=moderate, 3=high, 4=very high

    # VAD (Voice Activity Detection) settings
    vad_enabled: bool = True  # Enable VAD to remove silence before transcription
    vad_threshold: float = 0.5  # Speech probability threshold (0.0-1.0)
    min_silence_duration_ms: int = 800  # Min silence to mark speech end (milliseconds)
    min_speech_duration_ms: int = 500  # Min speech to start detection (milliseconds)

    # Auto-stop on silence
    auto_stop_enabled: bool = False  # Auto-stop recording after silence
    auto_stop_silence_sec: float = 2.0  # Seconds of silence before auto-stop

    # Hotkey settings
    hotkey: str = "ctrl+shift+space"  # Global hotkey to start/stop recording

    # Mouse button settings
    mouse_button: str = "middle"  # Mouse button for recording: none, left, middle, right, x1, x2
    enable_mouse_button: bool = False  # Enable mouse button recording

    # Behavior settings
    auto_copy: bool = True  # Auto copy to clipboard
    auto_paste: bool = True  # Auto paste to focused window
    auto_enter: bool = False  # Press Enter after paste

    # Paste method: "clipboard" (safe, uses Ctrl+Shift+V) or "type" (legacy, types characters)
    # "clipboard" is recommended - it's faster and doesn't crash terminal apps like Claude Code
    paste_method: str = "clipboard"  # clipboard | type
    paste_delay: float = 0.15  # Delay before paste (seconds) - allows window focus to settle

    # First run
    first_run: bool = True  # Show onboarding tooltip on first launch

    # Sound feedback
    sound_feedback: bool = True  # Play beep on start/stop recording

    # UI settings
    always_on_top: bool = True
    minimize_to_tray: bool = True
    show_notifications: bool = True
    dark_mode: bool = True

    # Statistics
    total_words: int = 0
    total_recordings: int = 0
    total_seconds_saved: float = 0.0

    # v3 modernization — Stage 0 flags (see План модернизации v3, Этап 0)
    research_mode: bool = False       # experiments only: hard-disables paste/clipboard
    audio_archive: bool = False       # opt-in raw-audio retention corpus
    audio_archive_dpapi: bool = True  # DPAPI encryption for the archive (opt-out checkbox)
    legacy_prompt_removed: bool = True  # off = restore the leaked "Диктовка..." cloud prompt

    # v3 modernization — Stage 1 flag (see План модернизации v3, Этап 1 / D3)
    # off = MME @ 16 kHz (v2 behaviour); on = WASAPI @ 48 kHz + FIR resample to
    # 16 kHz at stop(), with automatic visible MME fallback if the open fails.
    capture_wasapi: bool = False

    def __post_init__(self) -> None:
        # Non-field state guarding rate-limited disk writes.
        # Initialized once at construction, before any thread can call save().
        self._save_lock = threading.Lock()
        self._last_save_time = 0.0
        self._deferred_pending = False

    @classmethod
    def get_config_dir(cls) -> Path:
        """Get the configuration directory."""
        config_dir = Path(platformdirs.user_config_dir("WhisperTyping", "WhisperTyping"))
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir

    @classmethod
    def get_config_path(cls) -> Path:
        """Get the configuration file path."""
        return cls.get_config_dir() / "config.json"

    # Fields dropped in 2.4.0 together with the code that read them. Listed
    # explicitly so the migration log says what went, instead of silently
    # eating everything unknown.
    _REMOVED_FIELDS = (
        "enable_remote_fallback",
        "remote_server_url", "remote_url", "remote_timeout", "remote_api_key",
        "telegram_api_id", "telegram_api_hash", "telegram_chat_id",
        "telegram_bot_token", "telegram_enabled",
        "groq_api_key", "groq_model",
    )

    @classmethod
    def migrate(cls, data: dict) -> dict:
        """Bring a stored config dict up to CONFIG_VERSION.

        PURE SCHEMA WORK: no PortAudio, no device enumeration, nothing that
        needs hardware or optional imports — this runs on every start, in
        headless CI and in tests where `sounddevice` is not installed. The
        device index is only RENAMED here; resolving it to a real device is
        the audio layer's job, at stream open.
        """
        old_version = int(data.get("config_version", 1) or 1)
        changed = []

        if data.get("backend") not in BACKENDS:
            if "backend" in data:
                changed.append(f"backend={data['backend']}->sherpa")
            data["backend"] = "sherpa"
            # A cloud model id cannot survive the backend change.
            if data.get("model_size") not in SHERPA_MODELS:
                changed.append(f"model_size={data.get('model_size')}->giga-am-v3-ru-punct")
                data["model_size"] = "giga-am-v3-ru-punct"
        elif data.get("model_size") not in SHERPA_MODELS:
            changed.append(f"model_size={data.get('model_size')}->giga-am-v3-ru-punct")
            data["model_size"] = "giga-am-v3-ru-punct"

        if "audio_device" in data:
            legacy = data.pop("audio_device")
            try:
                legacy = int(legacy)
            except (TypeError, ValueError):
                legacy = -1
            data.setdefault("audio_device_legacy_index", legacy)
            data.setdefault("audio_device_name", "")
            data.setdefault("audio_hostapi", "")
            changed.append(f"audio_device={legacy}->legacy_index")

        known = {f.name for f in fields(cls)}
        for key in list(data):
            if key in known:
                continue
            changed.append(f"-{key}" if key in cls._REMOVED_FIELDS else f"-{key}(unknown)")
            data.pop(key)

        data["config_version"] = CONFIG_VERSION
        if changed or old_version != CONFIG_VERSION:
            logger.info("CONFIG_MIGRATED old=%s new=%s | %s",
                        old_version, CONFIG_VERSION, ", ".join(changed) or "no field changes")
        return data

    @classmethod
    def load(cls) -> "Config":
        """Load configuration from file."""
        config_path = cls.get_config_path()
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Unknown keys used to raise TypeError here and silently reset
                # the whole config — hotkey, mouse button and lifetime counters
                # included. Migration drops them by name instead.
                return cls(**cls.migrate(data))
            except (json.JSONDecodeError, TypeError, AttributeError) as e:
                logger.error("CONFIG_LOAD_FAILED | %s: %s — falling back to defaults",
                             type(e).__name__, e)
        return cls()

    def save(self) -> None:
        """Save configuration to file (rate-limited to avoid excessive disk I/O)."""
        with self._save_lock:
            now = time.time()
            if self._last_save_time and now - self._last_save_time < 0.5:
                if not self._deferred_pending:
                    self._deferred_pending = True
                    threading.Timer(1.0, self._deferred_flush).start()
                return
            self._last_save_time = now
            self._write_locked()

    def _deferred_flush(self):
        """Flush deferred save to disk."""
        with self._save_lock:
            self._deferred_pending = False
            self._last_save_time = time.time()
            self._write_locked()

    def _write_locked(self):
        """Write config to disk. Caller MUST hold self._save_lock."""
        config_path = self.get_config_path()
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)

    def update_stats(self, words: int, duration: float) -> None:
        """Update usage statistics."""
        self.total_words += words
        self.total_recordings += 1
        # Assume typing speed of 40 WPM, calculate time saved
        typing_time = (words / 40) * 60  # seconds
        self.total_seconds_saved += max(0, typing_time - duration)
        self.save()

    def apply_quality_profile(self, profile: str) -> None:
        """Apply quality profile preset to configuration.

        Args:
            profile: One of "fast", "balanced", "quality"
        """
        if profile not in QUALITY_PROFILES:
            profile = "balanced"

        settings = QUALITY_PROFILES[profile]
        self.quality_profile = profile
        self.backend = settings["backend"]
        self.model_size = settings["model_size"]
        self.vad_enabled = settings["vad_enabled"]
        self.vad_threshold = settings["vad_threshold"]
        self.min_silence_duration_ms = settings["min_silence_duration_ms"]
        self.enable_post_processing = settings["enable_post_processing"]
        self.save()


# The only backend since 2.4.0 (see src/backends/__init__.py)
BACKENDS = {
    "sherpa": "Sherpa-ONNX (GigaAM Russian)",
}

# Available Sherpa-ONNX models
SHERPA_MODELS = {
    "giga-am-v3-ru-punct": "GigaAM v3 Russian + Punctuation (2025-12, recommended)",
    "giga-am-v3-ru": "GigaAM v3 Russian (2025)",
    "giga-am-v2-ru": "GigaAM v2 Russian (2025)",
    "giga-am-ru": "GigaAM Russian (2024)",
}

# Supported languages
LANGUAGES = {
    "auto": "Auto-detect",
    "en": "English",
    "ru": "Russian",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "ar": "Arabic",
    "hi": "Hindi",
    "tr": "Turkish",
    "pl": "Polish",
    "uk": "Ukrainian",
    "nl": "Dutch",
    "sv": "Swedish",
    "cs": "Czech",
    "ro": "Romanian",
    "hu": "Hungarian",
    "el": "Greek",
    "fi": "Finnish",
    "da": "Danish",
    "no": "Norwegian",
    "th": "Thai",
    "vi": "Vietnamese",
    "id": "Indonesian",
    "ms": "Malay",
}

# Available mouse buttons for recording
MOUSE_BUTTONS = {
    "none": "Отключено",
    "left": "Левая кнопка",
    "middle": "Средняя кнопка (колесо)",
    "right": "Правая кнопка",
    "x1": "Кнопка X1 (вперед)",
    "x2": "Кнопка X2 (назад)",
}

# Available paste methods
PASTE_METHODS = {
    "clipboard": "Clipboard + Ctrl+Shift+V (рекомендуется)",
    "type": "Посимвольный ввод (может вызывать краши)",
}

# Quality profile presets
QUALITY_PROFILES = {
    "fast": {
        "backend": "sherpa",
        "model_size": "giga-am-v3-ru-punct",
        "vad_enabled": False,
        "vad_threshold": 0.5,
        "min_silence_duration_ms": 800,
        "enable_post_processing": False,
        "description": "⚡ Fast — Максимальная скорость",
    },
    "balanced": {
        "backend": "sherpa",
        "model_size": "giga-am-v3-ru-punct",
        "vad_enabled": True,
        "vad_threshold": 0.5,
        "min_silence_duration_ms": 800,
        "enable_post_processing": True,
        "description": "⚖️ Balanced — Баланс скорости и качества",
    },
    "quality": {
        "backend": "sherpa",
        "model_size": "giga-am-v3-ru-punct",
        "vad_enabled": True,
        "vad_threshold": 0.3,
        "min_silence_duration_ms": 500,
        "enable_post_processing": True,
        "description": "🎯 Quality — Максимальное качество (Sherpa)",
    },
}

# Model metadata for UI display (RAM usage, RTF, description)
MODEL_METADATA = {
    "giga-am-v3-ru-punct": {"ram_mb": 250, "rtf": 0.05, "description": "Русский + пунктуация (v3, 2025-12)"},
    "giga-am-v3-ru": {"ram_mb": 220, "rtf": 0.04, "description": "Русский (2025, CTC v3)"},
    "giga-am-v2-ru": {"ram_mb": 140, "rtf": 0.09, "description": "Русский (2025)"},
    "giga-am-ru": {"ram_mb": 140, "rtf": 0.1, "description": "Русский (2024)"},
}
