"""Whisper backend implementation using faster-whisper or openai-whisper."""
import gc
import threading
import time
from typing import Callable, Optional, Tuple
import numpy as np

from .base import BaseBackend

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


class WhisperBackend(BaseBackend):
    """Speech recognition backend using OpenAI Whisper."""

    def __init__(
        self,
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = "auto",
        language: str = "auto",
        on_progress: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(model_size, device, compute_type, language, on_progress)
        self._model = None
        self._loading = False
        self._lock = threading.Lock()
        self._detected_device = device
        self._detected_compute_type = compute_type

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

    def load_model(self):
        """Load the Whisper model."""
        if WHISPER_BACKEND is None:
            if self.on_progress:
                self.on_progress("Error: Whisper not installed")
            raise RuntimeError("Whisper not installed")

        with self._lock:
            if self._model is not None:
                return

            if self._loading:
                return

            self._loading = True

        try:
            device, compute_type = self._detect_device()
            self._detected_device = device
            self._detected_compute_type = compute_type

            if WHISPER_BACKEND == "faster-whisper":
                self._model = WhisperModel(
                    self.model_size,
                    device=device,
                    compute_type=compute_type
                )
            else:
                # OpenAI Whisper
                self._model = whisper.load_model(self.model_size, device=device)

        except Exception as e:
            if self.on_progress:
                self.on_progress(f"Error loading Whisper model: {e}")
            raise
        finally:
            self._loading = False

    def unload_model(self):
        """Unload the model to free memory."""
        with self._lock:
            self._model = None
            # Force garbage collection
            gc.collect()
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass

    def transcribe(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000
    ) -> Tuple[str, float]:
        """
        Transcribe audio to text.

        Args:
            audio: Audio data as numpy array
            sample_rate: Sample rate of the audio

        Returns:
            Tuple of (transcribed text, processing time in seconds)
        """
        if self._model is None:
            self.load_model()

        start_time = time.time()

        try:
            # Ensure audio is float32 and mono
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)

            if len(audio.shape) > 1:
                audio = audio.mean(axis=1)

            # Resample if necessary (Whisper expects 16kHz)
            if sample_rate != 16000:
                try:
                    # Use librosa if available (faster than scipy)
                    import librosa
                    audio = librosa.resample(audio, orig_sr=sample_rate, target_sr=16000)
                except ImportError:
                    # Fallback to scipy (slower)
                    try:
                        import scipy.signal
                        num_samples = int(len(audio) * 16000 / sample_rate)
                        audio = scipy.signal.resample(audio, num_samples)
                    except ImportError:
                        pass

            language = self.language if self.language != "auto" else None

            if WHISPER_BACKEND == "faster-whisper":
                segments, info = self._model.transcribe(
                    audio,
                    language=language,
                    beam_size=5,
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=500)
                )
                text = " ".join([segment.text for segment in segments]).strip()

            else:
                # OpenAI Whisper
                result = self._model.transcribe(
                    audio,
                    language=language,
                    fp16=False
                )
                text = result["text"].strip()

            process_time = time.time() - start_time

            return text, process_time

        except Exception as e:
            return "", 0.0

    def is_model_loaded(self) -> bool:
        """Check if model is loaded."""
        return self._model is not None

    def get_model_info(self) -> dict:
        """Get information about the current model."""
        info = super().get_model_info()
        info.update({
            "whisper_backend": WHISPER_BACKEND,
            "detected_device": self._detected_device,
            "detected_compute_type": self._detected_compute_type,
        })
        return info
