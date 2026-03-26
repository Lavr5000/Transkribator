"""Sherpa-ONNX backend implementation with GigaAM Russian models."""
import gc
import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional, Tuple
import numpy as np

from .base import BaseBackend

logger = logging.getLogger("transkribator")

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
        "giga-am-v3-ru": {
            "name": "GigaAM v3 Russian CTC (2025)",
            "url": "",
            "files": ["v3_ctc.int8.onnx", "tokens.txt"],
            "ctc_model_file": "v3_ctc.int8.onnx",
            "language": "ru",
        },
    }

    # Chunking: long audio is split to prevent ONNX crash
    CHUNK_DURATION_SEC = 25    # 25 seconds per chunk (safe for NeMo Transducer)
    CHUNK_THRESHOLD_SEC = 30   # Apply chunking only for audio longer than this
    CHUNK_SAMPLE_RATE = 16000  # Always 16kHz after resampling

    def __init__(
        self,
        model_size: str = "giga-am-v3-ru",
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

    def _get_model_dir(self) -> Path:
        """Get the model directory path."""
        if self.model_path:
            return Path(self.model_path)

        # Default: models/sherpa/{model-name}
        # In PyInstaller frozen build use exe directory; in dev use source root
        if hasattr(sys, '_MEIPASS'):
            base_dir = Path(sys._MEIPASS) / "models" / "sherpa"
        else:
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

        # Check for CTC model file (model-specific filename or default)
        ctc_filename = self.MODELS.get(self.model_size, {}).get("ctc_model_file", "model.int8.onnx")
        has_ctc = (model_dir / ctc_filename).exists() or (model_dir / "model.onnx").exists()

        # Check for encoder/decoder/joiner files (Transducer mode)
        has_transducer = (
            (model_dir / "encoder.int8.onnx").exists() or (model_dir / "encoder.onnx").exists()
        ) and (model_dir / "decoder.onnx").exists() and (model_dir / "joiner.onnx").exists()

        # Cache the result - either CTC or Transducer is OK
        self._model_files_checked = has_ctc or has_transducer
        return has_ctc or has_transducer

    def _get_vad_model_dir(self) -> Path:
        """Get Silero VAD model directory, download if missing."""
        from huggingface_hub import snapshot_download

        # In PyInstaller frozen build use exe directory; in dev use source root
        if hasattr(sys, '_MEIPASS'):
            vad_dir = Path(sys._MEIPASS) / "models" / "sherpa" / "silero-vad"
        else:
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
                logger.warning("VAD_DOWNLOAD_FAILED | %s", e)
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

            # Detect model type - CTC vs Transducer
            ctc_filename = self.MODELS.get(self.model_size, {}).get("ctc_model_file", "model.int8.onnx")
            model_file = model_dir / ctc_filename
            tokens_file = model_dir / "tokens.txt"

            if model_file.exists():
                # CTC model (GigaAM v2 CTC)
                self._recognizer = sherpa_onnx.OfflineRecognizer.from_nemo_ctc(
                    model=str(model_file),
                    tokens=str(tokens_file),
                    num_threads=self.num_threads,
                    sample_rate=16000,
                    feature_dim=80,
                    decoding_method="greedy_search",
                    debug=False,
                )
            else:
                # Transducer model (encoder/decoder/joiner)
                encoder_file = model_dir / "encoder.int8.onnx"
                if not encoder_file.exists():
                    encoder_file = model_dir / "encoder.onnx"

                decoder_file = model_dir / "decoder.onnx"
                joiner_file = model_dir / "joiner.onnx"

                self._recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
                    encoder=str(encoder_file),
                    decoder=str(decoder_file),
                    joiner=str(joiner_file),
                    tokens=str(tokens_file),
                    num_threads=self.num_threads,
                    sample_rate=16000,
                    model_type="transducer",
                    debug=False,
                )

            # Initialize Silero VAD if enabled
            self._vad = None
            if self._vad_enabled:
                try:
                    vad_dir = self._get_vad_model_dir()
                    # Find the VAD model file
                    vad_model_path = None
                    for name in ["silero_vad.onnx", "v4.onnx", "model.onnx"]:
                        candidate = vad_dir / name
                        if candidate.exists():
                            vad_model_path = candidate
                            break
                    if vad_model_path is None:
                        logger.warning("VAD_MODEL_NOT_FOUND | dir=%s", vad_dir)
                    else:
                        silero_config = sherpa_onnx.SileroVadModelConfig(
                            model=str(vad_model_path),
                            threshold=self._vad_threshold,
                            min_silence_duration=self._min_silence_duration_ms / 1000.0,
                            min_speech_duration=self._min_speech_duration_ms / 1000.0,
                        )
                        vad_config = sherpa_onnx.VadModelConfig(
                            silero_vad=silero_config,
                            sample_rate=16000,
                            num_threads=1,
                        )
                        self._vad = sherpa_onnx.VadModel.create(vad_config)
                        logger.debug("VAD_INIT | threshold=%.2f | model=%s", self._vad_threshold, vad_model_path.name)
                except Exception as e:
                    logger.warning("VAD_INIT_FAILED | %s", e)
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
            gc.collect()

    def _transcribe_single_chunk(self, chunk: np.ndarray, chunk_index: int) -> str:
        """Transcribe a single audio chunk with 1 retry on failure."""
        for attempt in range(2):
            try:
                stream = self._recognizer.create_stream()
                stream.accept_waveform(self.CHUNK_SAMPLE_RATE, chunk)
                self._recognizer.decode_stream(stream)
                return stream.result.text.strip()
            except Exception as e:
                if attempt == 0:
                    logger.warning("SHERPA_CHUNK_RETRY | chunk=%d | error=%s", chunk_index, e)
                else:
                    logger.warning("SHERPA_CHUNK_FAILED | chunk=%d | error=%s", chunk_index, e)
        return ""

    def _transcribe_chunks(self, audio: np.ndarray, cancel_event=None) -> str:
        """Split long audio into 25s chunks and transcribe each independently."""
        chunk_size = self.CHUNK_DURATION_SEC * self.CHUNK_SAMPLE_RATE  # 400 000 samples
        texts = []
        offset = 0
        chunk_index = 0
        while offset < len(audio):
            if cancel_event and cancel_event.is_set():
                logger.info("SHERPA_CHUNKS_CANCELLED | after %d chunks", chunk_index)
                break
            chunk = audio[offset: offset + chunk_size]
            if len(chunk) < 1600:   # Skip chunks < 0.1s (noise/silence tail)
                break
            chunk_text = self._transcribe_single_chunk(chunk, chunk_index)
            if chunk_text:
                texts.append(chunk_text)
            offset += chunk_size
            chunk_index += 1
        return " ".join(texts)

    def transcribe(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
        cancel_event=None
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

        audio_duration = len(audio) / sample_rate
        logger.info("SHERPA_START | model=%s | audio=%.1fs", self.model_size, audio_duration)

        start_time = time.time()

        try:
            # Ensure audio is float32 and mono
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)

            if len(audio.shape) > 1:
                audio = audio.mean(axis=1)

            # Pad with 200ms silence at start — CTC models need a clean onset
            # to properly align the first token (avoids dropping first 1-2 words)
            pad_samples = int(0.2 * 16000)  # 200ms = 3200 samples
            audio = np.concatenate([np.zeros(pad_samples, dtype=np.float32), audio])

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
                window_size = self._vad.window_size()
                speech_windows = []
                has_speech = False
                for i in range(0, len(audio), window_size):
                    window = audio[i:i + window_size]
                    if len(window) < window_size:
                        # Pad last window for VAD check
                        padded = np.zeros(window_size, dtype=np.float32)
                        padded[:len(window)] = window
                        is_speech = self._vad.is_speech(padded.tolist())
                    else:
                        is_speech = self._vad.is_speech(window.tolist())
                    if is_speech:
                        has_speech = True
                        speech_windows.append(audio[i:min(i + window_size, len(audio))])

                if has_speech and speech_windows:
                    audio = np.concatenate(speech_windows)
                    logger.debug("VAD_FILTER | kept %d/%d windows", len(speech_windows),
                                 len(audio) // window_size + 1)
                elif not has_speech:
                    logger.debug("VAD_NO_SPEECH | audio=%.1fs", len(audio) / 16000.0)
                    return "", 0.0
                self._vad.reset()

            # Route: chunk long audio to avoid ONNX crash
            audio_duration_sec = len(audio) / 16000.0
            if audio_duration_sec > self.CHUNK_THRESHOLD_SEC:
                text = self._transcribe_chunks(audio, cancel_event=cancel_event)
            else:
                stream = self._recognizer.create_stream()
                stream.accept_waveform(16000, audio)
                self._recognizer.decode_stream(stream)
                text = stream.result.text.strip()

            process_time = time.time() - start_time
            num_chunks = len(audio) // (self.CHUNK_DURATION_SEC * 16000) + 1 if audio_duration > self.CHUNK_THRESHOLD_SEC else 1
            logger.info("SHERPA_DONE | elapsed=%.2fs | chunks=%d | text_len=%d", process_time, num_chunks, len(text))

            return text, process_time

        except Exception as e:
            logger.error("SHERPA_FAILED | model=%s | audio=%.1fs | %s", self.model_size, audio_duration, e, exc_info=True)
            if self.on_progress:
                self.on_progress(f"Error: {e}")
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
