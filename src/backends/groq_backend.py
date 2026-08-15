"""Groq Whisper cloud backend with automatic Sherpa fallback."""
import io
import logging
import threading
import time
import wave
from typing import Callable, Optional, Tuple

import numpy as np

from .base import BaseBackend
from ..event_log import log_event

logger = logging.getLogger("transkribator")

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    Groq = None

GROQ_API_TIMEOUT = 15  # seconds (enough for ~2-3 min audio)
GROQ_FAILURE_COOLDOWN = 60  # seconds: after a failure, skip Groq and go straight to fallback

# Module-level failure state (single endpoint/key in this app).
# time.monotonic() — wall-clock jumps must not shorten/extend the cooldown.
_failure_lock = threading.Lock()
_last_failure_mono = 0.0


def _groq_in_cooldown() -> bool:
    with _failure_lock:
        return (time.monotonic() - _last_failure_mono) < GROQ_FAILURE_COOLDOWN if _last_failure_mono else False


def _mark_groq_failure():
    global _last_failure_mono
    with _failure_lock:
        _last_failure_mono = time.monotonic()


def _mark_groq_success():
    global _last_failure_mono
    with _failure_lock:
        _last_failure_mono = 0.0


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
        # Этап 0: legacy prompt was a proven leak source with zero measured
        # benefit (R6) — default removes it; off restores it for rollback.
        legacy_prompt_removed: bool = True,
    ):
        super().__init__(model_size, device, compute_type, language, on_progress)
        self._client = None
        self._fallback = None
        self.last_used_fallback = False  # True if last transcription used Sherpa fallback
        self.last_fallback_reason: Optional[str] = None
        self.last_prompt_sent: Optional[str] = None  # captured at request time, for prompt_version
        self.legacy_prompt_removed = legacy_prompt_removed

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
        """Resolve GROQ_API_KEY (environment-first, optional dev keystore)."""
        from ..dev_keys import load_env_var
        load_env_var("GROQ_API_KEY")

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
        self.last_fallback_reason = None
        # Legacy prompt is a proven leak source with zero measured benefit
        # (R6) — removed by default (Этап 0). Off restores it for rollback;
        # no glossary exists yet (Этап 3), so the only alternative is none.
        self.last_prompt_sent = None if self.legacy_prompt_removed else "Диктовка на русском языке."

        if cancel_event and cancel_event.is_set():
            self.last_fallback_reason = "cancelled"
            return "", 0.0

        if self._client is not None and _groq_in_cooldown():
            logger.info("GROQ_COOLDOWN | recent failure, using Sherpa fallback without network attempt")
            self.last_fallback_reason = "cooldown"
        elif self._client is not None:
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
                    prompt=self.last_prompt_sent,
                    timeout=GROQ_API_TIMEOUT,
                )
                text = resp.text.strip()
                elapsed = time.time() - start_time
                _mark_groq_success()
                logger.info("GROQ_API_OK | elapsed=%.2fs | text_len=%d", elapsed, len(text))
                return text, elapsed
            except Exception as e:
                _mark_groq_failure()
                self.last_fallback_reason = type(e).__name__
                logger.warning("GROQ_FALLBACK | reason=%s | falling back to sherpa (cooldown %ds)",
                               e, GROQ_FAILURE_COOLDOWN)
                if self.on_progress:
                    self.on_progress("Groq failed, using Sherpa...")

        # Fallback
        self.last_used_fallback = True
        log_event("fallback", backend="groq", reason=self.last_fallback_reason)
        fallback = self._get_fallback()
        if not fallback.is_model_loaded():
            fallback.load_model()
        return fallback.transcribe(audio, sample_rate, cancel_event=cancel_event)

    def get_model_info(self) -> dict:
        info = super().get_model_info()
        info["groq_connected"] = self._client is not None
        info["fallback_loaded"] = self._fallback is not None and self._fallback.is_model_loaded()
        return info
