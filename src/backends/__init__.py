"""Speech recognition backends for GolosText application.

This module provides a unified interface for multiple speech recognition backends:
- WhisperBackend: OpenAI Whisper implementation (using faster-whisper)
- SherpaBackend: Sherpa-ONNX with GigaAM models (optimized for Russian)
"""

from .base import BaseBackend
from .whisper_backend import WhisperBackend
from .sherpa_backend import SherpaBackend

__all__ = [
    "BaseBackend",
    "WhisperBackend",
    "SherpaBackend",
]

# Backend registry for dynamic loading
BACKENDS = {
    "whisper": WhisperBackend,
    "sherpa": SherpaBackend,
}

def get_backend(backend_name: str) -> type[BaseBackend]:
    """Get backend class by name.

    Args:
        backend_name: Name of the backend (whisper, sherpa)

    Returns:
        Backend class

    Raises:
        ValueError: If backend is not found
    """
    if backend_name not in BACKENDS:
        raise ValueError(
            f"Unknown backend: {backend_name}. "
            f"Available backends: {', '.join(BACKENDS.keys())}"
        )
    return BACKENDS[backend_name]
