"""Configuration management for WhisperTyping."""
import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
import platformdirs


@dataclass
class Config:
    """Application configuration."""

    # Quality profile (presets for Fast/Balanced/Quality)
    quality_profile: str = "quality"  # fast, balanced, quality (default: quality for max accuracy)

    # User-defined correction dictionary
    user_dictionary: list = field(default_factory=list)  # [{"wrong": str, "correct": str, "case_sensitive": bool}]

    # Backend selection
    backend: str = "sherpa"  # whisper, sherpa (sherpa is ~30% faster for Russian)

    # Model settings
    model_size: str = "giga-am-v2-ru"  # For Sherpa: giga-am-v2-ru (default), giga-am-ru
                                      # For Whisper: tiny, base, small, medium, large
                                      # For Podlodka: podlodka-turbo
    language: str = "auto"  # auto-detect or specific language code
    device: str = "auto"  # auto, cpu, cuda
    compute_type: str = "auto"  # auto, int8, float16, float32
    enable_post_processing: bool = True  # Enable text post-processing for better accuracy

    # Audio settings
    sample_rate: int = 16000
    channels: int = 1
    audio_device: int = -1  # -1 = system default, or specific device index
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

    # UI settings
    always_on_top: bool = True
    minimize_to_tray: bool = True
    show_notifications: bool = True
    dark_mode: bool = True

    # Statistics
    total_words: int = 0
    total_recordings: int = 0
    total_seconds_saved: float = 0.0

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

    @classmethod
    def load(cls) -> "Config":
        """Load configuration from file."""
        config_path = cls.get_config_path()
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # ALWAYS use "quality" as default (max quality)
                # Also update backend and model to match quality profile
                data["quality_profile"] = "quality"
                quality_settings = QUALITY_PROFILES["quality"]
                data["backend"] = quality_settings["backend"]
                data["model_size"] = quality_settings["model_size"]
                return cls(**data)
            except (json.JSONDecodeError, TypeError):
                pass
        return cls()

    def save(self) -> None:
        """Save configuration to file."""
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


# Available backends
BACKENDS = {
    "whisper": "Whisper (OpenAI)",
    "sherpa": "Sherpa-ONNX (GigaAM Russian)",
    "podlodka-turbo": "Whisper-Podlodka-Turbo (Russian fine-tuned)",
}

# Available Whisper models
WHISPER_MODELS = {
    "tiny": "Tiny (~1GB VRAM, fastest)",
    "base": "Base (~1GB VRAM, fast)",
    "small": "Small (~2GB VRAM, balanced)",
    "medium": "Medium (~5GB VRAM, accurate)",
    "large": "Large (~10GB VRAM, most accurate)",
    "large-v3": "Large V3 (~10GB VRAM, latest)"
}

# Available Sherpa-ONNX models
SHERPA_MODELS = {
    "giga-am-v2-ru": "GigaAM v2 Russian (2025, recommended)",
    "giga-am-ru": "GigaAM Russian (2024)",
}

# Available Podlodka-Turbo models
PODLODKA_MODELS = {
    "podlodka-turbo": "Podlodka-Turbo (Russian fine-tuned, recommended)",
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
        "model_size": "giga-am-v2-ru",
        "vad_enabled": False,
        "vad_threshold": 0.5,
        "min_silence_duration_ms": 800,
        "enable_post_processing": False,
        "description": "⚡ Fast — Максимальная скорость",
    },
    "balanced": {
        "backend": "sherpa",
        "model_size": "giga-am-v2-ru",
        "vad_enabled": True,
        "vad_threshold": 0.5,
        "min_silence_duration_ms": 800,
        "enable_post_processing": True,
        "description": "⚖️ Balanced — Баланс скорости и качества",
    },
    "quality": {
        "backend": "whisper",
        "model_size": "small",
        "vad_enabled": True,
        "vad_threshold": 0.3,
        "min_silence_duration_ms": 500,
        "enable_post_processing": True,
        "description": "🎯 Quality — Максимальное качество",
    },
}

# Model metadata for UI display (RAM usage, RTF, description)
MODEL_METADATA = {
    # Whisper models
    "tiny": {"ram_mb": 1000, "rtf": 0.3, "description": "Макс. скорость"},
    "base": {"ram_mb": 1000, "rtf": 0.5, "description": "Быстрый"},
    "small": {"ram_mb": 2000, "rtf": 1.0, "description": "Баланс"},
    "medium": {"ram_mb": 5000, "rtf": 2.0, "description": "Точный"},
    "large": {"ram_mb": 10000, "rtf": 3.0, "description": "Очень точный"},
    "large-v3": {"ram_mb": 10000, "rtf": 3.5, "description": "Последний (v3)"},
    "large-v3-turbo": {"ram_mb": 10000, "rtf": 3.0, "description": "Макс. точность"},
    # Sherpa models
    "giga-am-v2-ru": {"ram_mb": 140, "rtf": 0.1, "description": "Русский (2025)"},
    "giga-am-ru": {"ram_mb": 140, "rtf": 0.1, "description": "Русский (2024)"},
    # Podlodka model
    "podlodka-turbo": {"ram_mb": 1000, "rtf": 0.4, "description": "Ru fine-tuned"},
}
