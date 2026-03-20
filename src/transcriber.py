"""Transcription module with multi-backend support.

Supports multiple speech recognition backends:
- WhisperBackend: OpenAI Whisper (faster-whisper or openai-whisper)
- SherpaBackend: Sherpa-ONNX with GigaAM models (optimized for Russian)
"""
import gc
import logging
import threading
import time
from pathlib import Path
from typing import Callable, Optional, Tuple
import numpy as np

logger = logging.getLogger("transkribator")

from text_processor import AdvancedTextProcessor

# Try to import enhanced text processor with punctuation
try:
    from text_processor_enhanced import EnhancedTextProcessor
    ENHANCED_PROCESSOR_AVAILABLE = True
except ImportError:
    ENHANCED_PROCESSOR_AVAILABLE = False
from backends import get_backend, BaseBackend


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
        enable_post_processing: bool = True,
        # VAD parameters
        vad_enabled: bool = False,
        vad_threshold: float = 0.5,
        min_silence_duration_ms: int = 800,
        min_speech_duration_ms: int = 500,
        # User dictionary
        user_dictionary: list = None,
    ):
        """
        Initialize transcriber with specified backend.

        Args:
            backend: Backend name (whisper, sherpa, podlodka-turbo)
            model_size: Model size/identifier
            device: Device to use (cpu, cuda, auto)
            compute_type: Computation type (float16, int8, auto)
            language: Language code (ru, en, auto)
            on_progress: Callback for progress updates
            enable_post_processing: Enable text post-processing
            vad_enabled: Enable Voice Activity Detection
            vad_threshold: VAD probability threshold (0.0-1.0)
            min_silence_duration_ms: Min silence duration for VAD (ms)
            min_speech_duration_ms: Min speech duration for VAD (ms)
            user_dictionary: User-defined correction entries
        """
        self.backend_name = backend
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language if language != "auto" else None
        self.on_progress = on_progress

        # VAD configuration
        self.vad_enabled = vad_enabled
        self.vad_threshold = vad_threshold
        self.min_silence_duration_ms = min_silence_duration_ms
        self.min_speech_duration_ms = min_speech_duration_ms

        # User dictionary for custom corrections
        self.user_dictionary = user_dictionary or []

        # Fallback tracking
        self.last_used_fallback = False

        self._backend = None
        self._lock = threading.Lock()
        self._cancel_event = threading.Event()

        # Initialize text processor
        lang_code = language if language != "auto" else "ru"

        # Use EnhancedTextProcessor for Sherpa backend (better punctuation)
        # Use AdvancedTextProcessor for Whisper (already has punctuation)
        if backend == "sherpa" and ENHANCED_PROCESSOR_AVAILABLE:
            self.text_processor = EnhancedTextProcessor(
                language=lang_code,
                enable_corrections=enable_post_processing,
                enable_punctuation=True,  # Enable punctuation restoration
                user_dictionary=self.user_dictionary,
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
                on_progress=self.on_progress,
                # VAD config
                vad_enabled=self.vad_enabled,
                vad_threshold=self.vad_threshold,
                min_silence_duration_ms=self.min_silence_duration_ms,
                min_speech_duration_ms=self.min_speech_duration_ms,
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
            old_backend = self.backend_name
            if self._backend:
                try:
                    self._backend.unload_model()
                except Exception as e:
                    logger.warning("UNLOAD_FAILED | error=%s", e)

            # Update configuration
            self.backend_name = backend
            if model_size:
                self.model_size = model_size
            logger.info("BACKEND_SWITCH | %s → %s | model=%s", old_backend, backend, model_size or self.model_size)

            # Recreate text processor for new backend
            # Sherpa needs EnhancedTextProcessor (with punctuation)
            # Others use AdvancedTextProcessor (already have punctuation)
            lang_code = self.language or "ru"
            if backend == "sherpa" and ENHANCED_PROCESSOR_AVAILABLE:
                self.text_processor = EnhancedTextProcessor(
                    language=lang_code,
                    enable_corrections=self._enable_post_processing,
                    enable_punctuation=True,
                    user_dictionary=self.user_dictionary,
                )
            else:
                self.text_processor = AdvancedTextProcessor(
                    language=lang_code,
                    enable_corrections=self._enable_post_processing
                )

            # Create new backend
            self._create_backend()

    def cancel(self):
        """Signal cancellation for long-running transcription."""
        self._cancel_event.set()

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
        self._cancel_event.clear()

        if self._backend is None:
            self._create_backend()

        audio_duration = len(audio) / sample_rate
        logger.info("TRANSCRIBE_START | backend=%s | audio=%.1fs (%d samples) | sr=%d",
                     self.backend_name, audio_duration, len(audio), sample_rate)

        start_time = time.time()

        try:
            # Transcribe using backend (pass cancel event for chunked processing)
            text, backend_time = self._backend.transcribe(audio, sample_rate, cancel_event=self._cancel_event)

            # Track if Groq fell back to Sherpa
            self.last_used_fallback = getattr(self._backend, 'last_used_fallback', False)

            # Check cancellation after transcription
            if self._cancel_event.is_set():
                logger.info("TRANSCRIBE_CANCELLED | backend=%s", self.backend_name)
                return "", 0.0

            # Apply post-processing to improve text quality
            if self.enable_post_processing and self.text_processor:
                text = self.text_processor.process(text)

            process_time = time.time() - start_time
            logger.info("TRANSCRIBE_DONE | backend=%s | audio=%.1fs | elapsed=%.2fs (RTF=%.2f) | words=%d | \"%s\"",
                         self.backend_name, audio_duration, process_time,
                         process_time / audio_duration if audio_duration > 0 else 0,
                         len(text.split()), text[:50])
            return text, process_time

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error("TRANSCRIBE_FAILED | backend=%s | audio=%.1fs | elapsed=%.2fs | error=%s",
                          self.backend_name, audio_duration, elapsed, e, exc_info=True)
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
        logger.info("MODEL_LOAD_START | backend=%s | model=%s", self.backend_name, self.model_size)
        t0 = time.time()
        try:
            if self._backend:
                self._backend.load_model()
                logger.info("MODEL_LOAD_DONE | backend=%s | elapsed=%.2fs", self.backend_name, time.time() - t0)
                return True
            return False
        except Exception as e:
            logger.error("MODEL_LOAD_FAILED | backend=%s | elapsed=%.2fs | error=%s",
                          self.backend_name, time.time() - t0, e, exc_info=True)
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

    def set_user_dictionary(self, user_dictionary: list):
        """Update user dictionary for custom corrections.

        Args:
            user_dictionary: List of {"wrong": str, "correct": str, "case_sensitive": bool} entries
        """
        self.user_dictionary = user_dictionary or []
        if self.text_processor and hasattr(self.text_processor, 'set_user_dictionary'):
            self.text_processor.set_user_dictionary(self.user_dictionary)

    def get_user_dictionary(self) -> list:
        """Get current user dictionary."""
        return self.user_dictionary

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
