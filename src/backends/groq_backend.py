"""Groq Whisper cloud backend with automatic Sherpa fallback."""
import io
import logging
import os
import time
import wave
from pathlib import Path
from typing import Callable, Optional, Tuple

import numpy as np

from .base import BaseBackend

logger = logging.getLogger("transkribator")

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    Groq = None

GROQ_API_TIMEOUT = 15  # seconds (enough for ~2-3 min audio)


class GroqBackend(BaseBackend):
    """Cloud speech recognition via Groq Whisper API.
    Falls back to SherpaBackend on any failure."""

    def __init__(
        self,
        model_size: str = "whisper-large-v3-turbo",
        device: str = "auto",
        compute_type: str = "auto",
        language: str = "ru",
        on_progress: Optional[Callable[[str], None]] = None,
        # VAD params accepted for interface compatibility (unused by Groq)
        vad_enabled: bool = False,
        vad_threshold: float = 0.5,
        min_silence_duration_ms: int = 800,
        min_speech_duration_ms: int = 500,
    ):
        super().__init__(model_size, device, compute_type, language, on_progress)
        self._client = None
        self._fallback = None
        self.last_used_fallback = False  # True if last transcription used Sherpa fallback

    def _get_fallback(self):
        """Lazy-init SherpaBackend for fallback."""
        if self._fallback is None:
            from .sherpa_backend import SherpaBackend
            self._fallback = SherpaBackend(
                model_size="giga-am-v3-ru-punct",
                on_progress=self.on_progress,
            )
        return self._fallback

    @staticmethod
    def _ensure_groq_api_key():
        """Load GROQ_API_KEY from blogger .env if not already in environment."""
        if os.environ.get("GROQ_API_KEY"):
            return
        env_path = Path.home() / ".claude" / "0 ProEKTi" / "blogger" / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("GROQ_API_KEY="):
                    os.environ["GROQ_API_KEY"] = line.split("=", 1)[1].strip()
                    return

    def load_model(self):
        if not GROQ_AVAILABLE:
            logger.warning("groq package not installed, using Sherpa fallback")
            if self.on_progress:
                self.on_progress("Groq SDK not installed, using Sherpa fallback")
            self._get_fallback().load_model()
            return
        try:
            self._ensure_groq_api_key()
            self._client = Groq()  # reads GROQ_API_KEY from env
            if self.on_progress:
                self.on_progress("Groq Whisper ready")
        except Exception as e:
            logger.warning("Groq client init failed: %s", e)
            if self.on_progress:
                self.on_progress(f"Groq unavailable ({e}), using Sherpa")
            self._get_fallback().load_model()

    def unload_model(self):
        self._client = None
        if self._fallback is not None:
            self._fallback.unload_model()
            self._fallback = None

    def is_model_loaded(self) -> bool:
        return self._client is not None or (
            self._fallback is not None and self._fallback.is_model_loaded()
        )

    @staticmethod
    def _numpy_to_wav_bytes(audio: np.ndarray, sample_rate: int) -> bytes:
        """Convert numpy float32 array to WAV bytes in memory."""
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)
        if len(audio.shape) > 1:
            audio = audio.mean(axis=1)
        audio = np.clip(audio, -1.0, 1.0)
        pcm = (audio * 32767).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm.tobytes())
        buf.seek(0)
        return buf.read()

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000, cancel_event=None) -> Tuple[str, float]:
        start_time = time.time()
        self.last_used_fallback = False

        if cancel_event and cancel_event.is_set():
            return "", 0.0

        if self._client is not None:
            try:
                wav_bytes = self._numpy_to_wav_bytes(audio, sample_rate)
                audio_duration = len(audio) / sample_rate
                logger.info("GROQ_API_CALL | model=%s | audio=%.1fs | wav_size=%d bytes",
                            self.model_size, audio_duration, len(wav_bytes))
                resp = self._client.audio.transcriptions.create(
                    file=("audio.wav", wav_bytes),
                    model=self.model_size,
                    language=self.language if self.language != "auto" else None,
                    temperature=0.0,  # deterministic decoding reduces Russian hallucinations
                    prompt="Диктовка на русском языке.",  # hints Groq to expect RU dictation
                    timeout=GROQ_API_TIMEOUT,
                )
                text = resp.text.strip()
                elapsed = time.time() - start_time
                logger.info("GROQ_API_OK | elapsed=%.2fs | text_len=%d", elapsed, len(text))
                return text, elapsed
            except Exception as e:
                logger.warning("GROQ_FALLBACK | reason=%s | falling back to sherpa", e)
                if self.on_progress:
                    self.on_progress("Groq failed, using Sherpa...")

        # Fallback
        self.last_used_fallback = True
        fallback = self._get_fallback()
        if not fallback.is_model_loaded():
            fallback.load_model()
        return fallback.transcribe(audio, sample_rate, cancel_event=cancel_event)

    def get_model_info(self) -> dict:
        info = super().get_model_info()
        info["groq_connected"] = self._client is not None
        info["fallback_loaded"] = self._fallback is not None and self._fallback.is_model_loaded()
        return info
