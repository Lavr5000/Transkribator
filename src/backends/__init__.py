"""Speech recognition backends for GolosText application.

This module provides a unified interface for multiple speech recognition backends:
- WhisperBackend: OpenAI Whisper implementation (using faster-whisper)
- SherpaBackend: Sherpa-ONNX with GigaAM models (optimized for Russian)
- PodlodkaTurboBackend: Whisper-Podlodka-Turbo (Russian fine-tuned)
- GroqBackend: Groq Whisper cloud API with Sherpa fallback

Backends are imported LAZILY: importing this package must not pull optional
heavy dependencies (torch/transformers/faster_whisper add seconds of startup
and hundreds of MB of RAM). Only the backend actually requested is imported.
"""
import importlib
import importlib.util

from .base import BaseBackend

__all__ = [
    "BaseBackend",
    "WhisperBackend",
    "SherpaBackend",
    "PodlodkaTurboBackend",
    "GroqBackend",
    "BACKENDS",
    "get_backend",
    "backend_available",
]

# Backend registry: name -> (submodule, class name, core import the backend needs)
BACKENDS = {
    "whisper": ("whisper_backend", "WhisperBackend", "faster_whisper"),
    "sherpa": ("sherpa_backend", "SherpaBackend", "sherpa_onnx"),
    "podlodka-turbo": ("podlodka_turbo_backend", "PodlodkaTurboBackend", "transformers"),
    "groq": ("groq_backend", "GroqBackend", "groq"),
}

_CLASS_TO_NAME = {cls: name for name, (_, cls, _) in BACKENDS.items()}


def get_backend(backend_name: str) -> type:
    """Get backend class by name (imports the backend module on demand).

    Raises:
        ValueError: If backend is not found
    """
    if backend_name not in BACKENDS:
        raise ValueError(
            f"Unknown backend: {backend_name}. "
            f"Available backends: {', '.join(BACKENDS.keys())}"
        )
    module_name, class_name, _ = BACKENDS[backend_name]
    module = importlib.import_module(f".{module_name}", __name__)
    return getattr(module, class_name)


def backend_available(backend_name: str) -> bool:
    """True when the backend's core dependency is importable.

    Used by the UI to hide/disable backends that cannot work in this
    install (e.g. the frozen EXE ships sherpa only; whisper/podlodka/groq
    need a source install with the matching extra).
    """
    if backend_name not in BACKENDS:
        return False
    dep = BACKENDS[backend_name][2]
    try:
        return importlib.util.find_spec(dep) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


def __getattr__(name):  # PEP 562 — keep `from src.backends import WhisperBackend` working
    if name in _CLASS_TO_NAME:
        return get_backend(_CLASS_TO_NAME[name])
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
