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

from .crash_reporter import get_reporter

logger = logging.getLogger("transkribator")

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
        enable_post_processing: bool = True,
        # VAD parameters
        vad_enabled: bool = False,
        vad_threshold: float = 0.5,
        min_silence_duration_ms: int = 800,
        min_speech_duration_ms: int = 500,
        # User dictionary
        user_dictionary: list = None,
        # Этап 0: legacy Groq prompt removal (default on, see groq_backend.py)
        legacy_prompt_removed: bool = True,
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
        self.legacy_prompt_removed = legacy_prompt_removed

        # Fallback tracking
        self.last_used_fallback = False

        self._backend = None
        self._lock = threading.Lock()
        self._cancel_event = threading.Event()

        # Set BEFORE building the processor (factory reads it)
        self._enable_post_processing = enable_post_processing

        # Single post-processing point: backends return RAW model output,
        # the Transcriber-level processor is the only one that runs.
        self.text_processor = self._make_text_processor()

        # Create backend instance
        self._create_backend()

    def _make_text_processor(self, backend_name: str = None, model_size: str = None):
        """Build the backend-aware text processor (single construction point)."""
        lang_code = self.language or "ru"
        if ENHANCED_PROCESSOR_AVAILABLE:
            return EnhancedTextProcessor(
                language=lang_code,
                enable_corrections=self._enable_post_processing,
                backend=backend_name or self.backend_name,
                model_size=model_size or self.model_size,
                user_dictionary=self.user_dictionary,
            )
        return AdvancedTextProcessor(
            language=lang_code,
            enable_corrections=self._enable_post_processing,
        )

    def _backend_fingerprint(self) -> tuple:
        """All parameters that flow into backend construction.

        switch_backend() is a no-op while this fingerprint is unchanged;
        changing ANY of these (not just backend/model) must rebuild.
        """
        return (
            self.backend_name,
            self.model_size,
            self.device,
            self.compute_type,
            self.language,
            self.vad_enabled,
            self.vad_threshold,
            self.min_silence_duration_ms,
            self.min_speech_duration_ms,
            self.legacy_prompt_removed,
        )

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
                legacy_prompt_removed=self.legacy_prompt_removed,
            )
            self._created_fingerprint = self._backend_fingerprint()

        except Exception as e:
            if self.on_progress:
                self.on_progress(f"Error creating backend: {e}")
            raise

    def switch_backend(
        self,
        backend: str,
        model_size: Optional[str] = None
    ) -> bool:
        """
        Switch to a different backend with rollback on failure.

        Non-blocking: if a transcription currently holds the engine lock,
        returns False immediately ("busy") instead of freezing the caller
        (settings handlers run on the GUI thread).

        No-op fingerprint guard: re-applying identical settings does NOT
        reload the model.

        Args:
            backend: New backend name (whisper, sherpa, podlodka-turbo)
            model_size: Optional new model size

        Returns:
            True — switched (or nothing to change), False — engine busy.
        Raises on backend construction failure (state rolled back).
        """
        if not self._lock.acquire(blocking=False):
            logger.warning("BACKEND_SWITCH_BUSY | transcription in progress, switch to %s rejected", backend)
            return False
        try:
            # Save old state for rollback
            old_backend_name = self.backend_name
            old_model_size = self.model_size
            old_backend_instance = self._backend
            old_processor = self.text_processor

            # No-op guard: identical construction fingerprint + live backend
            candidate_fp = (backend, model_size or old_model_size) + self._backend_fingerprint()[2:]
            if (
                self._backend is not None
                and getattr(self, "_created_fingerprint", None) == candidate_fp
            ):
                logger.info("BACKEND_SWITCH_NOOP | %s/%s unchanged", backend, model_size or old_model_size)
                return True

            cr = get_reporter()
            if cr:
                cr.set_context("BACKEND_SWITCH", backend=backend, model=model_size or self.model_size, previous_backend=old_backend_name)

            logger.info("BACKEND_SWITCH | %s → %s | model=%s", old_backend_name, backend, model_size or self.model_size)

            try:
                # Update configuration
                self.backend_name = backend
                if model_size:
                    self.model_size = model_size

                # Recreate text processor for new backend/model
                self.text_processor = self._make_text_processor()

                # Create new backend (may raise)
                self._create_backend()

            except Exception:
                # Rollback: restore old state
                logger.error("BACKEND_SWITCH_ROLLBACK | %s → %s failed, restoring %s",
                             old_backend_name, backend, old_backend_name)
                self.backend_name = old_backend_name
                self.model_size = old_model_size
                self._backend = old_backend_instance
                self.text_processor = old_processor
                raise

            # Success: unload old backend now
            if old_backend_instance and old_backend_instance is not self._backend:
                try:
                    old_backend_instance.unload_model()
                except Exception as e:
                    logger.warning("UNLOAD_OLD_BACKEND_FAILED | error=%s", e)
            return True
        finally:
            self._lock.release()

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

        audio_duration = len(audio) / sample_rate
        cr = get_reporter()
        if cr:
            cr.set_context("TRANSCRIBE", backend=self.backend_name, model=self.model_size, audio_duration_sec=round(audio_duration, 1))
        logger.info("TRANSCRIBE_START | backend=%s | audio=%.1fs (%d samples) | sr=%d",
                     self.backend_name, audio_duration, len(audio), sample_rate)

        start_time = time.time()

        try:
            # Hold the engine lock for the whole inference: switch_backend()
            # can never unload a model mid-decode (it try-acquires and
            # returns busy instead of blocking the GUI thread).
            with self._lock:
                if self._backend is None:
                    self._create_backend()
                text, backend_time = self._backend.transcribe(audio, sample_rate, cancel_event=self._cancel_event)

                # Track if Groq fell back to Sherpa
                self.last_used_fallback = getattr(self._backend, 'last_used_fallback', False)
                self.last_fallback_reason = getattr(self._backend, 'last_fallback_reason', None)
                self.last_prompt_sent = getattr(self._backend, 'last_prompt_sent', None)

                # Groq's local fallback is Sherpa v3-punct: rebuild the processor
                # so backend-aware config matches the text that was actually produced
                if self.last_used_fallback and self.backend_name == "groq" and ENHANCED_PROCESSOR_AVAILABLE:
                    if getattr(self.text_processor, "backend", None) != "sherpa":
                        self.text_processor = self._make_text_processor(
                            backend_name="sherpa",
                            model_size="giga-am-v3-ru-punct",
                        )
                        logger.info("GROQ_FALLBACK_PROCESSOR_SWITCH | processor rebuilt for sherpa fallback")

            # Check cancellation after transcription
            if self._cancel_event.is_set():
                logger.info("TRANSCRIBE_CANCELLED | backend=%s", self.backend_name)
                return "", 0.0

            # Apply post-processing to improve text quality
            if self.enable_post_processing and self.text_processor:
                text = self.text_processor.process(text)

            process_time = time.time() - start_time
            logger.info("TRANSCRIBE_DONE | backend=%s | audio=%.1fs | elapsed=%.2fs (RTF=%.2f) | words=%d | chars=%d",
                         self.backend_name, audio_duration, process_time,
                         process_time / audio_duration if audio_duration > 0 else 0,
                         len(text.split()), len(text))
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
    """Get list of registered backend names."""
    from .backends import BACKENDS
    return list(BACKENDS.keys())


def get_backend_info(backend_name: str) -> dict:
    """Get information about a specific backend."""
    try:
        backend_class = get_backend(backend_name)

        # Create temporary instance to get info
        temp_backend = backend_class()
        return temp_backend.get_model_info()

    except Exception:
        return {"error": f"Backend {backend_name} not available"}
