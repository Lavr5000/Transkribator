"""Podlodka-Turbo backend implementation - Russian fine-tuned Whisper."""
import gc
import threading
import time
from typing import Callable, Optional, Tuple
import numpy as np

from .base import BaseBackend

try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False


class PodlodkaTurboBackend(BaseBackend):
    """Speech recognition backend using Whisper-Podlodka-Turbo (Russian fine-tuned).

    This model is fine-tuned by bond005 specifically for Russian language,
    based on Whisper large-v3-turbo. Expected to provide better accuracy
    for Russian speech than standard Whisper models.
    """

    def __init__(
        self,
        model_size: str = "podlodka-turbo",
        device: str = "auto",
        compute_type: str = "auto",
        language: str = "ru",
        on_progress: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(model_size, device, compute_type, language, on_progress)
        self._model = None
        self._loading = False
        self._lock = threading.Lock()
        self._detected_device = device
        self._detected_compute_type = compute_type

        # Force Russian for Podlodka-Turbo
        self.language = "ru"

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
        """Load the Whisper-Podlodka-Turbo model."""
        if not FASTER_WHISPER_AVAILABLE:
            if self.on_progress:
                self.on_progress("Error: faster-whisper not installed")
            raise RuntimeError("faster-whisper not installed")

        with self._lock:
            if self._model is not None:
                return

            if self._loading:
                return

            self._loading = True

        try:
            if self.on_progress:
                self.on_progress("Loading Whisper-Podlodka-Turbo model (Russian fine-tuned)...")

            device, compute_type = self._detect_device()
            self._detected_device = device
            self._detected_compute_type = compute_type

            # Load Podlodka-Turbo model from HuggingFace
            model_path = "bond005/whisper-podlodka-turbo"

            self._model = WhisperModel(
                model_path,
                device=device,
                compute_type=compute_type
            )

            if self.on_progress:
                self.on_progress(f"Whisper-Podlodka-Turbo loaded ({device})")

        except Exception as e:
            if self.on_progress:
                self.on_progress(f"Error loading Podlodka-Turbo: {e}")
            raise
        finally:
            self._loading = False

    def unload_model(self):
        """Unload the model to free memory."""
        with self._lock:
            self._model = None
            gc.collect()
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass

        if self.on_progress:
            self.on_progress("Podlodka-Turbo model unloaded")

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
            if self.on_progress:
                self.on_progress("Transcribing with Podlodka-Turbo...")

            # Ensure audio is float32 and mono
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)

            if len(audio.shape) > 1:
                audio = audio.mean(axis=1)

            # Resample if necessary
            if sample_rate != 16000:
                try:
                    import scipy.signal
                    num_samples = int(len(audio) * 16000 / sample_rate)
                    audio = scipy.signal.resample(audio, num_samples)
                except ImportError:
                    pass

            # Transcribe with Russian language specified
            segments, info = self._model.transcribe(
                audio,
                language="ru",  # Force Russian
                beam_size=5,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500)
            )
            text = " ".join([segment.text for segment in segments]).strip()

            process_time = time.time() - start_time

            if self.on_progress:
                self.on_progress(f"Podlodka-Turbo done ({process_time:.1f}s)")

            return text, process_time

        except Exception as e:
            if self.on_progress:
                self.on_progress(f"Podlodka-Turbo error: {e}")
            return "", 0.0

    def is_model_loaded(self) -> bool:
        """Check if model is loaded."""
        return self._model is not None

    def get_model_info(self) -> dict:
        """Get information about the current model."""
        info = super().get_model_info()
        info.update({
            "whisper_backend": "faster-whisper (podlodka-turbo)",
            "detected_device": self._detected_device,
            "detected_compute_type": self._detected_compute_type,
            "model_source": "HuggingFace: bond005/whisper-podlodka-turbo",
            "language": "ru (Russian fine-tuned)",
        })
        return info
