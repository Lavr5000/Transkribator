"""Podlodka-Turbo backend implementation - Russian fine-tuned Whisper."""
import gc
import threading
import time
from typing import Callable, Optional, Tuple
import numpy as np

from .base import BaseBackend

try:
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor
    import torch
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

try:
    import scipy.signal
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


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
        self._processor = None
        self._loading = False
        self._lock = threading.Lock()
        self._detected_device = device
        self._dtype = "float32"

        # Force Russian for Podlodka-Turbo
        self.language = "ru"

    def _detect_device(self) -> Tuple[str, str]:
        """Detect the best device and dtype."""
        device = self.device
        dtype = self._dtype

        if device == "auto":
            if torch.cuda.is_available():
                device = "cuda"
                dtype = "float16"
            else:
                device = "cpu"
                dtype = "float32"

        return device, dtype

    def load_model(self):
        """Load the Whisper-Podlodka-Turbo model using transformers."""
        if not TRANSFORMERS_AVAILABLE:
            if self.on_progress:
                self.on_progress("Error: transformers not installed")
            raise RuntimeError("transformers not installed. Install: pip install transformers torch")

        with self._lock:
            if self._model is not None:
                return

            if self._loading:
                return

            self._loading = True

        try:
            if self.on_progress:
                self.on_progress("Loading Whisper-Podlodka-Turbo model (Russian fine-tuned)...")

            device, dtype = self._detect_device()
            self._detected_device = device
            self._dtype = dtype

            model_id = "bond005/whisper-podlodka-turbo"

            # Load model
            torch_dtype = getattr(torch, dtype)
            self._model = AutoModelForSpeechSeq2Seq.from_pretrained(
                model_id,
                torch_dtype=torch_dtype,
                low_cpu_mem_usage=True,
                use_safetensors=True
            ).to(device)

            # Load processor
            self._processor = AutoProcessor.from_pretrained(model_id)

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
            self._processor = None
            gc.collect()
            try:
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except (RuntimeError, AttributeError):
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
                if SCIPY_AVAILABLE:
                    num_samples = int(len(audio) * 16000 / sample_rate)
                    audio = scipy.signal.resample(audio, num_samples)
                else:
                    # Simple linear interpolation
                    import math
                    ratio = 16000 / sample_rate
                    num_samples = int(len(audio) * ratio)
                    indices = np.linspace(0, len(audio) - 1, num_samples)
                    audio = np.interp(indices, np.arange(len(audio)), audio)

            # Prepare input
            inputs = self._processor(
                audio,
                sampling_rate=16000,
                return_tensors="pt"
            ).to(self._model.device)

            # Generate transcription
            with torch.no_grad():
                predicted_ids = self._model.generate(
                    **inputs,
                    language="ru",
                    task="transcribe",
                    do_sample=False,
                    temperature=1.0,
                )

            # Decode
            text = self._processor.batch_decode(predicted_ids, skip_special_tokens=True)[0]

            # Clean up text
            text = text.strip()

            process_time = time.time() - start_time

            if self.on_progress:
                self.on_progress(f"Podlodka-Turbo done ({process_time:.1f}s)")

            return text, process_time

        except Exception as e:
            if self.on_progress:
                self.on_progress(f"Podlodka-Turbo error: {e}")
            import traceback
            traceback.print_exc()
            return "", 0.0

    def is_model_loaded(self) -> bool:
        """Check if model is loaded."""
        return self._model is not None

    def get_model_info(self) -> dict:
        """Get information about the current model."""
        info = super().get_model_info()
        info.update({
            "whisper_backend": "transformers (podlodka-turbo)",
            "detected_device": self._detected_device,
            "dtype": self._dtype,
            "model_source": "HuggingFace: bond005/whisper-podlodka-turbo",
            "language": "ru (Russian fine-tuned)",
        })
        return info
