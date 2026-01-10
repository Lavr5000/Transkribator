"""Transcription module using Whisper."""
import os
import threading
import time
from pathlib import Path
from typing import Callable, Optional, Tuple
import numpy as np

from .text_processor import AdvancedTextProcessor

# Try faster-whisper first, fallback to openai-whisper
WHISPER_BACKEND = None

try:
    from faster_whisper import WhisperModel
    WHISPER_BACKEND = "faster-whisper"
except ImportError:
    try:
        import whisper
        WHISPER_BACKEND = "openai-whisper"
    except ImportError:
        pass


class Transcriber:
    """Transcribes audio using Whisper."""

    def __init__(
        self,
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = "auto",
        language: str = "auto",
        on_progress: Optional[Callable[[str], None]] = None,
        enable_post_processing: bool = True
    ):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language if language != "auto" else None
        self.on_progress = on_progress
        self.enable_post_processing = enable_post_processing

        self._model = None
        self._loading = False
        self._lock = threading.Lock()

        # Initialize text processor
        lang_code = language if language != "auto" else "ru"
        self.text_processor = AdvancedTextProcessor(
            language=lang_code,
            enable_corrections=enable_post_processing
        )

    def _detect_device(self) -> Tuple[str, str]:
        """Detect the best device and compute type."""
        device = self.device
        compute_type = self.compute_type

        if device == "auto":
            try:
                import torch
                if torch.cuda.is_available():
                    device = "cuda"
                else:
                    device = "cpu"
            except ImportError:
                device = "cpu"

        if compute_type == "auto":
            if device == "cuda":
                compute_type = "float16"
            else:
                compute_type = "int8"

        return device, compute_type

    def load_model(self) -> bool:
        """Load the Whisper model."""
        if WHISPER_BACKEND is None:
            if self.on_progress:
                self.on_progress("Error: Whisper not installed")
            return False

        with self._lock:
            if self._model is not None:
                return True

            if self._loading:
                return False

            self._loading = True

        try:
            if self.on_progress:
                self.on_progress(f"Loading {self.model_size} model...")

            device, compute_type = self._detect_device()

            if WHISPER_BACKEND == "faster-whisper":
                self._model = WhisperModel(
                    self.model_size,
                    device=device,
                    compute_type=compute_type
                )
            else:
                # OpenAI Whisper
                self._model = whisper.load_model(self.model_size, device=device)

            if self.on_progress:
                self.on_progress(f"Model loaded ({device})")

            return True

        except Exception as e:
            if self.on_progress:
                self.on_progress(f"Error loading model: {e}")
            return False

        finally:
            self._loading = False

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
        if self._model is None:
            if not self.load_model():
                return "", 0.0

        start_time = time.time()

        try:
            if self.on_progress:
                self.on_progress("Transcribing...")

            # Ensure audio is float32 and mono
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)

            if len(audio.shape) > 1:
                audio = audio.mean(axis=1)

            # Resample if necessary (Whisper expects 16kHz)
            if sample_rate != 16000:
                try:
                    import scipy.signal
                    num_samples = int(len(audio) * 16000 / sample_rate)
                    audio = scipy.signal.resample(audio, num_samples)
                except ImportError:
                    pass

            if WHISPER_BACKEND == "faster-whisper":
                segments, info = self._model.transcribe(
                    audio,
                    language=self.language,
                    beam_size=5,
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=500)
                )
                text = " ".join([segment.text for segment in segments]).strip()

            else:
                # OpenAI Whisper
                result = self._model.transcribe(
                    audio,
                    language=self.language,
                    fp16=False
                )
                text = result["text"].strip()

            # Apply post-processing to improve text quality
            if self.enable_post_processing and self.text_processor:
                text = self.text_processor.process(text)

            process_time = time.time() - start_time

            if self.on_progress:
                self.on_progress(f"Done ({process_time:.1f}s)")

            return text, process_time

        except Exception as e:
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
        """Check if model is loaded."""
        return self._model is not None

    @property
    def is_loading(self) -> bool:
        """Check if model is currently loading."""
        return self._loading

    def unload_model(self) -> None:
        """Unload the model to free memory."""
        with self._lock:
            self._model = None
            # Force garbage collection
            import gc
            gc.collect()
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass


def get_available_backend() -> Optional[str]:
    """Get the available Whisper backend."""
    return WHISPER_BACKEND
