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
    mic_boost: float = 20.0  # Software gain multiplier (increase if mic is too quiet)

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
