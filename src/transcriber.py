"""Transcription module with multi-backend support.

Supports multiple speech recognition backends:
- WhisperBackend: OpenAI Whisper (faster-whisper or openai-whisper)
- SherpaBackend: Sherpa-ONNX with GigaAM models (optimized for Russian)
"""
import gc
import threading
import time
from pathlib import Path
from typing import Callable, Optional, Tuple
import numpy as np

from .text_processor import AdvancedTextProcessor

# Try to import enhanced text processor with punctuation
try:
    from .text_processor_enhanced import EnhancedTextProcessor
    ENHANCED_PROCESSOR_AVAILABLE = True
except ImportError:
    ENHANCED_PROCESSOR_AVAILABLE = False
from .backends import get_backend, BaseBackend


class Transcriber:
    """Transcribes audio using configurable backend."""

    def __init__(
        self,
        backend: str = "whisper",
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = "auto",
        language: str = "auto",
        on_progress: Optional[Callable[[str], None]] = None,
        enable_post_processing: bool = True
    ):
        """
        Initialize transcriber with specified backend.

        Args:
            backend: Backend name (whisper, sherpa)
            model_size: Model size/identifier
            device: Device to use (cpu, cuda, auto)
            compute_type: Computation type (float16, int8, auto)
            language: Language code (ru, en, auto)
            on_progress: Callback for progress updates
            enable_post_processing: Enable text post-processing
        """
        self.backend_name = backend
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language if language != "auto" else None
        self.on_progress = on_progress

        self._backend = None
        self._lock = threading.Lock()

        # Initialize text processor
        lang_code = language if language != "auto" else "ru"

        # Use EnhancedTextProcessor for Sherpa backend (better punctuation)
        # Use AdvancedTextProcessor for Whisper (already has punctuation)
        if backend == "sherpa" and ENHANCED_PROCESSOR_AVAILABLE:
            self.text_processor = EnhancedTextProcessor(
                language=lang_code,
                enable_corrections=enable_post_processing,
                enable_punctuation=True  # Enable punctuation restoration
            )
        else:
            self.text_processor = AdvancedTextProcessor(
                language=lang_code,
                enable_corrections=enable_post_processing
            )

        # NOW set enable_post_processing (after text_processor is initialized)
        self._enable_post_processing = enable_post_processing

        # Create backend instance
        self._create_backend()

    def _create_backend(self):
        """Create backend instance based on configuration."""
        try:
            backend_class = get_backend(self.backend_name)
            self._backend = backend_class(
                model_size=self.model_size,
                device=self.device,
                compute_type=self.compute_type,
                language=self.language or "auto",
                on_progress=self.on_progress
            )

        except Exception as e:
            if self.on_progress:
                self.on_progress(f"Error creating backend: {e}")
            raise

    def switch_backend(
        self,
        backend: str,
        model_size: Optional[str] = None
    ):
        """
        Switch to a different backend.

        Args:
            backend: New backend name (whisper, sherpa, podlodka-turbo)
            model_size: Optional new model size
        """
        with self._lock:
            # Unload current backend
            if self._backend:
                try:
                    self._backend.unload_model()
                except Exception:
                    pass

            # Update configuration
            self.backend_name = backend
            if model_size:
                self.model_size = model_size

            # Recreate text processor for new backend
            # Sherpa needs EnhancedTextProcessor (with punctuation)
            # Others use AdvancedTextProcessor (already have punctuation)
            lang_code = self.language or "ru"
            if backend == "sherpa" and ENHANCED_PROCESSOR_AVAILABLE:
                self.text_processor = EnhancedTextProcessor(
                    language=lang_code,
                    enable_corrections=self._enable_post_processing,
                    enable_punctuation=True
                )
            else:
                self.text_processor = AdvancedTextProcessor(
                    language=lang_code,
                    enable_corrections=self._enable_post_processing
                )

            # Create new backend
            self._create_backend()

    def transcribe(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000
    ) -> Tuple[str, float]:
        """
        Transcribe audio data.

        Args:
            audio: Audio data as numpy array
            sample_rate: Sample rate of the audio

        Returns:
            Tuple of (transcribed text, processing time in seconds)
        """
        with open("debug.log", "a") as f:
            f.write(f"[DEBUG] Transcriber.transcribe called. Backend: {self.backend_name}, Audio shape: {audio.shape}, SR: {sample_rate}\n")

        if self._backend is None:
            with open("debug.log", "a") as f:
                f.write("[DEBUG] Backend is None, creating...\n")
            self._create_backend()

        start_time = time.time()

        try:
            # Transcribe using backend
            with open("debug.log", "a") as f:
                f.write(f"[DEBUG] Calling backend.transcribe...\n")

            text, backend_time = self._backend.transcribe(audio, sample_rate)

            with open("debug.log", "a") as f:
                f.write(f"[DEBUG] Backend returned text: '{text[:100] if text else '(empty)'}', Time: {backend_time}s\n")

            # Apply post-processing to improve text quality
            if self.enable_post_processing and self.text_processor:
                with open("debug.log", "a") as f:
                    f.write(f"[DEBUG] Applying post-processing...\n")
                text = self.text_processor.process(text)
                with open("debug.log", "a") as f:
                    f.write(f"[DEBUG] Post-processing done: '{text[:100]}'\n")

            process_time = time.time() - start_time

            # Don't send "Done" progress - it interferes with final "Готово" status
            # The main_window handles final status display

            return text, process_time

        except Exception as e:
            with open("debug.log", "a") as f:
                f.write(f"[ERROR] Transcriber.transcribe exception: {e}\n")
                import traceback
                f.write(f"[ERROR] Traceback: {traceback.format_exc()}\n")
            if self.on_progress:
                self.on_progress(f"Error: {e}")
            return "", 0.0

    def transcribe_file(self, filepath: Path) -> Tuple[str, float]:
        """Transcribe an audio file."""
        try:
            import soundfile as sf
            audio, sample_rate = sf.read(str(filepath))
            return self.transcribe(audio, sample_rate)
        except Exception as e:
            if self.on_progress:
                self.on_progress(f"Error reading file: {e}")
            return "", 0.0

    @property
    def is_loaded(self) -> bool:
        """Check if backend model is loaded."""
        return self._backend is not None and self._backend.is_model_loaded()

    def load_model(self) -> bool:
        """Load the backend model."""
        try:
            with open("debug.log", "a") as f:
                f.write(f"[DEBUG] Loading model. Backend: {self.backend_name}, Backend exists: {self._backend is not None}\n")

            if self._backend:
                self._backend.load_model()
                with open("debug.log", "a") as f:
                    f.write(f"[DEBUG] Model loaded successfully\n")
                return True

            with open("debug.log", "a") as f:
                f.write(f"[DEBUG] Backend is None, cannot load model\n")
            return False
        except Exception as e:
            with open("debug.log", "a") as f:
                f.write(f"[ERROR] Failed to load model: {e}\n")
                import traceback
                f.write(f"[ERROR] Traceback: {traceback.format_exc()}\n")
            return False

    def unload_model(self) -> None:
        """Unload the backend model to free memory."""
        with self._lock:
            if self._backend:
                self._backend.unload_model()
            # Force garbage collection
            gc.collect()
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass

    def get_backend_info(self) -> dict:
        """Get information about the current backend."""
        if self._backend:
            return self._backend.get_model_info()
        return {}

    @property
    def enable_post_processing(self) -> bool:
        """Get post-processing enabled state."""
        return self._enable_post_processing

    @enable_post_processing.setter
    def enable_post_processing(self, value: bool):
        """Set post-processing enabled state."""
        self._enable_post_processing = value
        if self.text_processor:
            self.text_processor.enable_corrections = value

    # Private field declaration
    _enable_post_processing: bool = True


def get_available_backends() -> list:
    """Get list of available backends."""
    return ["whisper", "sherpa"]


def get_backend_info(backend_name: str) -> dict:
    """Get information about a specific backend."""
    try:
        backend_class = get_backend(backend_name)

        # Create temporary instance to get info
        temp_backend = backend_class()
        return temp_backend.get_model_info()

    except Exception:
        return {"error": f"Backend {backend_name} not available"}
