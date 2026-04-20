"""Whisper backend implementation using faster-whisper or openai-whisper."""
import gc
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional, Tuple
import numpy as np

from .base import BaseBackend

# Import enhanced text processor
try:
    from src.text_processor_enhanced import EnhancedTextProcessor
    ENHANCED_PROCESSOR_AVAILABLE = True
except ImportError:
    from src.text_processor import AdvancedTextProcessor
    ENHANCED_PROCESSOR_AVAILABLE = False

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
        language: str = "ru",  # Changed from "auto" - force Russian for accuracy
        on_progress: Optional[Callable[[str], None]] = None,
        # VAD parameters
        vad_enabled: bool = False,
        vad_threshold: float = 0.5,
        min_silence_duration_ms: int = 800,
        min_speech_duration_ms: int = 500,
    ):
        super().__init__(model_size, device, compute_type, language, on_progress)
        self._model = None
        self._loading = False
        self._lock = threading.Lock()
        self._detected_device = device
        self._detected_compute_type = compute_type

        # VAD (Voice Activity Detection)
        self._vad = None
        self._vad_enabled = vad_enabled
        self._vad_threshold = vad_threshold
        self._min_silence_duration_ms = min_silence_duration_ms
        self._min_speech_duration_ms = min_speech_duration_ms

        # Initialize text processor with backend-aware configuration
        if ENHANCED_PROCESSOR_AVAILABLE:
            self.text_processor = EnhancedTextProcessor(
                language=language,
                backend=self.backend_name
            )
        else:
            self.text_processor = AdvancedTextProcessor(language=language)

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

    def _get_vad_model_dir(self) -> Path:
        """Get Silero VAD model directory, download if missing."""
        from huggingface_hub import snapshot_download

        # In PyInstaller frozen build use exe directory; in dev use source root
        if hasattr(sys, '_MEIPASS'):
            vad_dir = Path(sys.executable).parent / "models" / "sherpa" / "silero-vad"
        else:
            vad_dir = Path(__file__).parent.parent.parent / "models" / "sherpa" / "silero-vad"
        vad_dir.mkdir(parents=True, exist_ok=True)

        if not any((vad_dir / n).exists() for n in ("silero_vad.onnx", "v4.onnx", "model.onnx")):
            try:
                snapshot_download(
                    repo_id="deepghs/silero-vad-onnx",
                    local_dir=str(vad_dir),
                    local_dir_use_symlinks=False,
                )
            except Exception as e:
                print(f"Failed to download VAD model: {e}")

        return vad_dir

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

            # Initialize Silero VAD if enabled
            self._vad = None
            if self._vad_enabled:
                try:
                    vad_dir = self._get_vad_model_dir()
                    vad_model_path = None
                    for name in ("silero_vad.onnx", "v4.onnx", "model.onnx"):
                        candidate = vad_dir / name
                        if candidate.exists():
                            vad_model_path = candidate
                            break
                    if vad_model_path is None:
                        print(f"WhisperBackend: VAD model not found in {vad_dir}")
                    else:
                        import sherpa_onnx
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
                        print(f"WhisperBackend: VAD initialized ({vad_model_path.name})")
                except Exception as e:
                    print(f"WhisperBackend: Failed to initialize VAD: {e}")
                    self._vad = None

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
        sample_rate: int = 16000,
        cancel_event=None
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

            # Resample if necessary (Whisper & VAD expect 16kHz)
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

            # Apply VAD to filter silence if enabled (after resample to 16kHz)
            if self._vad_enabled and self._vad is not None:
                try:
                    window_size = self._vad.window_size()
                    speech_windows = []
                    has_speech = False
                    for i in range(0, len(audio), window_size):
                        window = audio[i:i + window_size]
                        if len(window) < window_size:
                            padded = np.zeros(window_size, dtype=np.float32)
                            padded[:len(window)] = window
                            is_speech = self._vad.is_speech(padded.tolist())
                        else:
                            is_speech = self._vad.is_speech(window.tolist())
                        if is_speech:
                            has_speech = True
                            speech_windows.append(audio[i:min(i + window_size, len(audio))])
                    self._vad.reset()
                    if has_speech and speech_windows:
                        audio = np.concatenate(speech_windows)
                    else:
                        return "", 0.0
                except Exception as e:
                    print(f"WhisperBackend: VAD filtering failed: {e}")
                    # Continue with original audio on VAD failure

            language = "ru"  # Force Russian for optimal accuracy

            if WHISPER_BACKEND == "faster-whisper":
                segments, info = self._model.transcribe(
                    audio,
                    language=language,
                    beam_size=5,  # Quality mode - optimal for Russian accuracy
                    temperature=0.0,  # Deterministic decoding, no hallucinations
                    vad_filter=True,
                    vad_parameters=dict(
                        min_silence_duration_ms=300,  # Optimized for Russian speech patterns
                        speech_pad_ms=400,  # Prevents cutting off word endings
                    )
                )
                text = " ".join([segment.text for segment in segments]).strip()

            else:
                # OpenAI Whisper
                result = self._model.transcribe(
                    audio,
                    language=language,
                    temperature=0.0,  # Add deterministic decoding
                    fp16=False
                )
                text = result["text"].strip()

            # Apply text post-processing (backend-aware)
            if hasattr(self, 'text_processor') and self.text_processor:
                text = self.text_processor.process(text)

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
