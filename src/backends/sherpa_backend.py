"""Sherpa-ONNX backend implementation with GigaAM Russian models."""
import os
import threading
import time
from pathlib import Path
from typing import Callable, Optional, Tuple
import numpy as np

from .base import BaseBackend

try:
    import sherpa_onnx
    SHERPA_AVAILABLE = True
except ImportError:
    SHERPA_AVAILABLE = False


class SherpaBackend(BaseBackend):
    """Speech recognition backend using Sherpa-ONNX with GigaAM models.

    This backend is optimized for Russian language recognition using
    GigaAM v2 models from Salute-developers.
    """

    # Default model configurations
    MODELS = {
        "giga-am-v2-ru": {
            "name": "GigaAM v2 Russian (2025-04-19)",
            "url": "https://huggingface.co/csukuangfj/sherpa-onnx-nemo-ctc-giga-am-v2-russian-2025-04-19",
            "files": [
                "model.onnx",
                "tokens.txt",
                "config.json"
            ],
            "language": "ru",
        },
        "giga-am-ru": {
            "name": "GigaAM Russian (2024-10-24)",
            "url": "https://huggingface.co/csukuangfj/sherpa-onnx-nemo-ctc-giga-am-russian-2024-10-24",
            "files": [
                "model.onnx",
                "tokens.txt",
                "config.json"
            ],
            "language": "ru",
        },
    }

    def __init__(
        self,
        model_size: str = "giga-am-v2-ru",
        device: str = "auto",
        compute_type: str = "auto",
        language: str = "auto",
        on_progress: Optional[Callable[[str], None]] = None,
        model_path: Optional[str] = None,
    ):
        """
        Initialize Sherpa-ONNX backend.

        Args:
            model_size: Model identifier (giga-am-v2-ru, giga-am-ru)
            device: Device to use (cpu only for ONNX)
            compute_type: Ignored for ONNX (always optimized)
            language: Language code (auto defaults to ru for GigaAM)
            on_progress: Callback for progress updates
            model_path: Optional path to model directory (if not default)
        """
        super().__init__(model_size, device, compute_type, language, on_progress)
        self.model_path = model_path
        self._recognizer = None
        self._loading = False
        self._lock = threading.Lock()

        # Force Russian language for GigaAM models
        if self.model_size.startswith("giga-am"):
            self.language = "ru"

    def _get_model_dir(self) -> Path:
        """Get the model directory path."""
        if self.model_path:
            return Path(self.model_path)

        # Default: models/sherpa/{model-name}
        base_dir = Path(__file__).parent.parent.parent / "models" / "sherpa"
        return base_dir / self.model_size

    def _check_model_files(self) -> bool:
        """Check if required model files exist."""
        model_dir = self._get_model_dir()

        if not model_dir.exists():
            return False

        # Check for tokens.txt (essential)
        if not (model_dir / "tokens.txt").exists():
            return False

        # Check for model.onnx or model.int8.onnx (both are valid)
        has_model = (model_dir / "model.onnx").exists() or (model_dir / "model.int8.onnx").exists()

        return has_model

    def load_model(self):
        """Load the Sherpa-ONNX model."""
        if not SHERPA_AVAILABLE:
            if self.on_progress:
                self.on_progress("Error: sherpa-onnx not installed")
            raise RuntimeError("sherpa-onnx not installed. Run: pip install sherpa-onnx")

        with self._lock:
            if self._recognizer is not None:
                return

            if self._loading:
                return

            self._loading = True

        try:
            if self.on_progress:
                self.on_progress(f"Loading Sherpa-ONNX {self.model_size}...")

            model_dir = self._get_model_dir()

            # Check if model exists
            if not self._check_model_files():
                raise FileNotFoundError(
                    f"Model files not found in {model_dir}. "
                    f"Please download the model first. "
                    f"See: {self.MODELS.get(self.model_size, {}).get('url', '')}"
                )

            # Detect model file (model.onnx or model.int8.onnx)
            model_file = model_dir / "model.onnx"
            if not model_file.exists():
                model_file = model_dir / "model.int8.onnx"

            tokens_file = model_dir / "tokens.txt"

            # Create recognizer using factory method for NeMo CTC models
            self._recognizer = sherpa_onnx.OfflineRecognizer.from_nemo_ctc(
                model=str(model_file),
                tokens=str(tokens_file),
                num_threads=2,
                sample_rate=16000,
                feature_dim=80,
                decoding_method="greedy_search",
                debug=False,
            )

            if self.on_progress:
                self.on_progress(f"Sherpa-ONNX {self.model_size} loaded")

        except Exception as e:
            if self.on_progress:
                self.on_progress(f"Error loading Sherpa-ONNX: {e}")
            raise
        finally:
            self._loading = False

    def unload_model(self):
        """Unload the model to free memory."""
        with self._lock:
            self._recognizer = None

        if self.on_progress:
            self.on_progress("Sherpa-ONNX model unloaded")

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
        """
        if self._recognizer is None:
            self.load_model()

        start_time = time.time()

        try:
            if self.on_progress:
                self.on_progress("Transcribing with Sherpa-ONNX...")

            # Ensure audio is float32 and mono
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)

            if len(audio.shape) > 1:
                audio = audio.mean(axis=1)

            # Resample if necessary (Sherpa-ONNX expects 16kHz)
            if sample_rate != 16000:
                try:
                    import scipy.signal
                    num_samples = int(len(audio) * 16000 / sample_rate)
                    audio = scipy.signal.resample(audio, num_samples)
                except ImportError:
                    pass

            # Create audio stream from numpy array
            # Sherpa-ONNX expects float32 audio normalized to [-1, 1]
            stream = self._recognizer.create_stream()
            stream.accept_waveform(16000, audio)

            # Decode stream (singular!)
            self._recognizer.decode_stream(stream)

            text = stream.result.text.strip()

            process_time = time.time() - start_time

            if self.on_progress:
                self.on_progress(f"Sherpa-ONNX done ({process_time:.1f}s)")

            return text, process_time

        except Exception as e:
            if self.on_progress:
                self.on_progress(f"Sherpa-ONNX error: {e}")
            return "", 0.0

    def is_model_loaded(self) -> bool:
        """Check if model is loaded."""
        return self._recognizer is not None

    def get_model_info(self) -> dict:
        """Get information about the current model."""
        info = super().get_model_info()
        info.update({
            "model_path": str(self._get_model_dir()),
            "model_files_exist": self._check_model_files(),
        })

        if self.model_size in self.MODELS:
            info["model_name"] = self.MODELS[self.model_size]["name"]
            info["model_url"] = self.MODELS[self.model_size]["url"]

        return info

    @classmethod
    def get_available_models(cls) -> dict:
        """Get list of available model configurations."""
        return cls.MODELS.copy()

    @classmethod
    def download_model(cls, model_name: str, target_dir: Optional[Path] = None) -> Path:
        """
        Download Sherpa-ONNX model from HuggingFace.

        Args:
            model_name: Model identifier (e.g., giga-am-v2-ru)
            target_dir: Target directory (default: models/sherpa/{model_name})

        Returns:
            Path to downloaded model directory

        Raises:
            ValueError: If model name is unknown
            RuntimeError: If download fails
        """
        if model_name not in cls.MODELS:
            raise ValueError(f"Unknown model: {model_name}. Available: {list(cls.MODELS.keys())}")

        if target_dir is None:
            target_dir = Path(__file__).parent.parent.parent / "models" / "sherpa" / model_name

        target_dir.mkdir(parents=True, exist_ok=True)

        try:
            from huggingface_hub import snapshot_download

            repo_id = cls.MODELS[model_name]["url"].split("huggingface.co/")[-1]

            snapshot_download(
                repo_id=repo_id,
                local_dir=str(target_dir),
                local_dir_use_symlinks=False,
            )

            return target_dir

        except ImportError:
            raise RuntimeError(
                "huggingface_hub not installed. "
                "Run: pip install huggingface_hub"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to download model: {e}")
