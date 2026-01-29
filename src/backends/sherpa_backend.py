"""Sherpa-ONNX backend implementation with GigaAM Russian models."""
import os
import threading
import time
from pathlib import Path
from typing import Callable, Optional, Tuple
import numpy as np

from .base import BaseBackend

# Import enhanced text processor for better punctuation
try:
    from ..text_processor_enhanced import EnhancedTextProcessor
    ENHANCED_PROCESSOR_AVAILABLE = True
except ImportError:
    from ..text_processor import AdvancedTextProcessor
    ENHANCED_PROCESSOR_AVAILABLE = False

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
            "name": "GigaAM v2 Russian Transducer (2025-04-19)",
            "url": "https://huggingface.co/csukuangfj/sherpa-onnx-nemo-transducer-giga-am-v2-russian-2025-04-19",
            "files": [
                "encoder.int8.onnx",
                "decoder.onnx",
                "joiner.onnx",
                "tokens.txt"
            ],
            "language": "ru",
        },
        "giga-am-ru": {
            "name": "GigaAM Russian Transducer (2024-10-24)",
            "url": "https://huggingface.co/csukuangfj/sherpa-onnx-nemo-transducer-giga-am-russian-2024-10-24",
            "files": [
                "encoder.int8.onnx",
                "decoder.onnx",
                "joiner.onnx",
                "tokens.txt"
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
        num_threads: Optional[int] = None,
        # VAD parameters
        vad_enabled: bool = False,
        vad_threshold: float = 0.5,
        min_silence_duration_ms: int = 800,
        min_speech_duration_ms: int = 500,
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
            num_threads: Number of threads for ONNX runtime (default: cpu_count)
            vad_enabled: Enable Voice Activity Detection
            vad_threshold: VAD probability threshold (0.0-1.0)
            min_silence_duration_ms: Min silence duration for VAD (ms)
            min_speech_duration_ms: Min speech duration for VAD (ms)
        """
        super().__init__(model_size, device, compute_type, language, on_progress)
        self.model_path = model_path
        # Auto-detect optimal thread count (default to cpu_count, max 8 for stability)
        cpu_count = os.cpu_count() or 4
        self.num_threads = max(1, min(num_threads or cpu_count, 8)) if num_threads is not None else max(1, min(cpu_count, 8))
        self._recognizer = None
        self._loading = False
        self._lock = threading.Lock()
        # Cache for model files check result
        self._model_files_checked = None

        # VAD (Voice Activity Detection) - set from parameters
        self._vad = None
        self._vad_enabled = vad_enabled
        self._vad_threshold = vad_threshold
        self._min_silence_duration_ms = min_silence_duration_ms
        self._min_speech_duration_ms = min_speech_duration_ms

        # Force Russian language for GigaAM models
        if self.model_size.startswith("giga-am"):
            self.language = "ru"

        # Initialize text processor with backend-aware configuration
        if ENHANCED_PROCESSOR_AVAILABLE:
            self.text_processor = EnhancedTextProcessor(
                language=self.language,
                backend=self.backend_name
            )
        else:
            self.text_processor = AdvancedTextProcessor(language=self.language)

    def _get_model_dir(self) -> Path:
        """Get the model directory path."""
        if self.model_path:
            return Path(self.model_path)

        # Default: models/sherpa/{model-name}
        base_dir = Path(__file__).parent.parent.parent / "models" / "sherpa"
        return base_dir / self.model_size

    def _check_model_files(self) -> bool:
        """Check if required model files exist (with caching)."""
        # Return cached result if available
        if self._model_files_checked is not None:
            return self._model_files_checked

        model_dir = self._get_model_dir()

        if not model_dir.exists():
            self._model_files_checked = False
            return False

        # Check for tokens.txt (essential)
        if not (model_dir / "tokens.txt").exists():
            self._model_files_checked = False
            return False

        # Check for encoder/decoder/joiner files (Transducer mode)
        has_transducer = (
            (model_dir / "encoder.int8.onnx").exists() or (model_dir / "encoder.onnx").exists()
        ) and (model_dir / "decoder.onnx").exists() and (model_dir / "joiner.onnx").exists()

        # Cache the result
        self._model_files_checked = has_transducer
        return has_transducer

    def _get_vad_model_dir(self) -> Path:
        """Get Silero VAD model directory, download if missing."""
        from huggingface_hub import snapshot_download

        vad_dir = Path(__file__).parent.parent.parent / "models" / "sherpa" / "silero-vad"
        vad_dir.mkdir(parents=True, exist_ok=True)

        # Check if model exists, download if missing
        if not (vad_dir / "v4.onnx").exists():
            try:
                snapshot_download(
                    repo_id="csukuangfj/sherpa-onnx-silero-vad",
                    local_dir=str(vad_dir),
                    local_dir_use_symlinks=False,
                )
            except Exception as e:
                print(f"Failed to download VAD model: {e}")
                # Return directory anyway - OfflineVad will fail gracefully

        return vad_dir

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
            model_dir = self._get_model_dir()

            # Check if model exists
            if not self._check_model_files():
                raise FileNotFoundError(
                    f"Model files not found in {model_dir}. "
                    f"Please download the model first. "
                    f"See: {self.MODELS.get(self.model_size, {}).get('url', '')}"
                )

            # Detect model files for Transducer mode
            encoder_file = model_dir / "encoder.int8.onnx"
            if not encoder_file.exists():
                encoder_file = model_dir / "encoder.onnx"

            decoder_file = model_dir / "decoder.onnx"
            joiner_file = model_dir / "joiner.onnx"
            tokens_file = model_dir / "tokens.txt"

            # Create recognizer using Transducer mode (GigaAM v2 is Transducer, NOT CTC!)
            self._recognizer = sherpa_onnx.OfflineRecognizer.from_nemo_transducer(
                encoder=str(encoder_file),
                decoder=str(decoder_file),
                joiner=str(joiner_file),
                tokens=str(tokens_file),
                num_threads=self.num_threads,
                sample_rate=16000,
                max_active_paths=4,  # Optimal balance of speed vs accuracy for Russian
                debug=False,
            )

            # Initialize Silero VAD if enabled
            self._vad = None
            if self._vad_enabled:
                try:
                    vad_dir = self._get_vad_model_dir()
                    self._vad = sherpa_onnx.OfflineVad(
                        model_dir=str(vad_dir),
                        threshold=self._vad_threshold,
                        min_silence_duration=self._min_silence_duration_ms / 1000.0,  # Convert to seconds
                        min_speech_duration=self._min_speech_duration_ms / 1000.0,
                    )
                    print(f"VAD initialized: threshold={self._vad_threshold}")
                except Exception as e:
                    print(f"Failed to initialize VAD: {e}")
                    self._vad = None

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
            # Ensure audio is float32 and mono
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)

            if len(audio.shape) > 1:
                audio = audio.mean(axis=1)

            # Resample if necessary (Sherpa-ONNX expects 16kHz)
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

            # Apply VAD to filter silence if enabled
            if self._vad_enabled and self._vad is not None:
                vad_stream = self._vad.create_stream()
                vad_stream.accept_waveform(16000, audio)

                # Flush to process remaining audio
                self._vad.compute(vad_stream)

                # Get speech segments
                segments = vad_stream.segments

                if segments:
                    # Concatenate only speech segments (remove silence)
                    speech_segments = []
                    for seg in segments:
                        start_sample = int(seg.start * 16000)
                        end_sample = int(seg.end * 16000)
                        # Ensure indices are within bounds
                        start_sample = max(0, start_sample)
                        end_sample = min(len(audio), end_sample)
                        if end_sample > start_sample:
                            speech_segments.append(audio[start_sample:end_sample])

                    if speech_segments:
                        audio = np.concatenate(speech_segments)
                    else:
                        # No speech detected
                        return "", 0.0
                else:
                    # No speech segments detected
                    return "", 0.0

            # Create audio stream from numpy array
            # Sherpa-ONNX expects float32 audio normalized to [-1, 1]
            stream = self._recognizer.create_stream()
            stream.accept_waveform(16000, audio)

            # Decode stream (singular!)
            self._recognizer.decode_stream(stream)

            text = stream.result.text.strip()

            # Apply text post-processing (backend-aware)
            if hasattr(self, 'text_processor') and self.text_processor:
                text = self.text_processor.process(text)

            process_time = time.time() - start_time

            return text, process_time

        except Exception as e:
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
