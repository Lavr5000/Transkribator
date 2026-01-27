"""Abstract base class for speech recognition backends."""
from abc import ABC, abstractmethod
from typing import Callable, Optional, Tuple
import numpy as np


class BaseBackend(ABC):
    """Abstract base class for speech recognition backends.

    All backends must implement this interface to ensure compatibility
    with the Transcriber class.
    """

    def __init__(
        self,
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = "auto",
        language: str = "auto",
        on_progress: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize backend.

        Args:
            model_size: Model size/identifier (e.g., base, small, giga-am-v2)
            device: Device to use (cpu, cuda, auto)
            compute_type: Computation type (float16, int8, auto)
            language: Language code (ru, en, auto)
            on_progress: Callback for progress updates
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.on_progress = on_progress

    @abstractmethod
    def load_model(self):
        """Load model into memory.

        This method should be called before transcribe().
        """
        pass

    @abstractmethod
    def unload_model(self):
        """Unload model from memory to free resources.

        This method should be called when switching backends or closing application.
        """
        pass

    @abstractmethod
    def transcribe(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000
    ) -> Tuple[str, float]:
        """
        Transcribe audio to text.

        Args:
            audio: Audio data as numpy array (float32, normalized to [-1, 1])
            sample_rate: Sample rate in Hz (default: 16000)

        Returns:
            Tuple of (transcribed_text, processing_time_seconds)

        Raises:
            Exception: If transcription fails
        """
        pass

    def get_model_info(self) -> dict:
        """Get information about the current model.

        Returns:
            Dictionary with model information (name, size, language, etc.)
        """
        return {
            "backend": self.__class__.__name__,
            "model_size": self.model_size,
            "language": self.language,
            "device": self.device,
        }

    def is_model_loaded(self) -> bool:
        """Check if model is currently loaded in memory.

        Returns:
            True if model is loaded, False otherwise
        """
        raise NotImplementedError("Subclasses must implement is_model_loaded()")
