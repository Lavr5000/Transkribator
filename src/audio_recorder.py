"""Audio recording module for WhisperTyping.

Persistent-stream architecture (2026-07-12): the microphone stream is opened
ONCE (in the background) and stays running for the recorder's lifetime;
start()/stop() only gate frames into a per-recording buffer. Rationale:
WASAPI device open/close can stall for 25+ seconds when the Windows audio
stack degrades, and per-recording open also loses the speech onset. While
idle the callback keeps a ~0.4s pre-roll ring buffer (RAM-only, never
persisted) so the first word spoken right at the hotkey press is captured.
"""
import collections
import logging
import math
import queue
import threading
import time
import tempfile
from pathlib import Path
from typing import Callable, Optional, Tuple
import numpy as np

from .event_log import log_event
from .resampler import StreamingResampler

logger = logging.getLogger("transkribator")

DBFS_FLOOR = -120.0  # clamp for zero/near-zero signal, avoids -inf in JSON

try:
    import sounddevice as sd
    import soundfile as sf
    AUDIO_AVAILABLE = True
except (ImportError, OSError):
    AUDIO_AVAILABLE = False

# WebRTC noise suppression (optional - may not be available on all platforms)
_WEBRTC_AVAILABLE = False
try:
    from webrtc_noise_gain import AudioProcessor
    _WEBRTC_AVAILABLE = True
except (ImportError, OSError):
    pass  # WebRTC not available, will use software boost only


class AudioRecorder:
    """Records audio from a persistent microphone stream.

    When webrtc_enabled=True (default):
    - WebRTC Noise Suppression removes background noise
    - WebRTC AGC normalizes audio to -3 dBFS target automatically
    - mic_boost parameter is ignored (AGC handles gain)

    When webrtc_enabled=False (fallback):
    - Raw audio capture with optional software mic_boost

    Internal chunk contract: every chunk in the recording buffer — pre-roll
    frames, WebRTC-processed frames, raw frames — is np.float32 of shape
    (n, 1), so np.concatenate(axis=0) is uniform.
    """

    PREROLL_SEC = 0.4            # pre-roll ring retention, rate-independent
    PREROLL_MAX_SAMPLES = 6400   # ~0.4s @ 16 kHz; rescaled per capture rate
    CALLBACK_STALL_SEC = 2.0     # active stream with no callbacks = dead
    WASAPI_RATE = 48000          # Stage 1: this device rejects 16 kHz on WASAPI (R1)
    WASAPI_BLOCKSIZE = 960       # 20 ms @ 48 kHz -> ~30 ms worst-case tail loss
    RECOVER_IDLE_GRACE_S = 60.0  # no recovery probe within 60 s of a stop()
    OPEN_RETRY_DELAY_S = 1.0     # settle time before the single WASAPI retry

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        on_level_update: Optional[Callable[[float], None]] = None,
        device: Optional[int] = None,
        mic_boost: float = 1.0,  # Software gain (DEPRECATED - only used when webrtc_enabled=False)
        webrtc_enabled: bool = True,
        noise_suppression_level: int = 2,
        auto_gain_dbfs: int = 3,
        capture_wasapi: bool = False,
        device_name: str = "",
        device_hostapi: str = "",
        on_device_resolved: Optional[Callable[[str, str], None]] = None,
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.on_level_update = on_level_update
        # Devices are addressed by host API + name; `device` is only the legacy
        # PortAudio index from a <= 2.3 config, used once and then written back
        # as a name through on_device_resolved.
        self.device = device
        self.device_name = device_name or ""
        self.device_hostapi = device_hostapi or ""
        self.on_device_resolved = on_device_resolved
        self.device_warning: Optional[str] = None
        self.mic_boost = mic_boost
        self.webrtc_enabled = webrtc_enabled and _WEBRTC_AVAILABLE
        self.noise_suppression_level = noise_suppression_level
        self._webrtc_processor = None

        self._recording = False
        self._closed = False  # permanent: set only by close_stream() on app quit
        self._audio_queue: queue.Queue = queue.Queue(maxsize=500)
        self._audio_data: list = []
        self._collect_thread: Optional[threading.Thread] = None

        # Persistent stream state
        self._stream = None
        self._stream_ok = False
        self._stream_opening = False
        self._stream_opened_at = 0.0
        self._last_callback_ts = 0.0
        # Bumped on every activation. A retiring stream's finished_callback
        # fires while its replacement is already live, so the callback must
        # know which stream it belongs to before clearing _stream_ok.
        self._stream_token = 0
        self._last_stop_ts = 0.0      # monotonic; idle grace for recovery
        self._fallback_since = 0.0    # monotonic; feeds capture_recovered.sticky_s
        self._recovering = False      # a try_recover_wasapi() is in flight

        # Locks. _lock: recording start/stop state. _state_lock: micro-lock
        # making callback vs start/stop transitions atomic (held microseconds).
        # _stream_lock: stream open/close (may be held 25s during a degraded
        # open — start()/stop() never acquire it). _open_flag_lock: guards
        # _stream_opening only.
        self._lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._stream_lock = threading.Lock()
        self._open_flag_lock = threading.Lock()

        # Pre-roll ring buffer (raw frames, RAM-only, ~0.4s retention)
        self._preroll: collections.deque = collections.deque()
        self._preroll_samples = 0

        # Audio quality tracking
        self.clipping_detected = False  # Peak > 0.95
        self.low_signal = False  # RMS < 0.005 for > 2 seconds
        self.capture_degraded = False  # stream died during a recording session
        self._low_signal_frames = 0  # Counter for consecutive low-signal frames
        self._low_signal_threshold = 0.005
        self._clipping_threshold = 0.95

        # Drop counters (fixes B10) — plain ints, incremented in the audio
        # callback with no lock (Этап 0 rule: instrumentation must not
        # perturb what it measures). Approximate under a genuine race is
        # acceptable; exactness is not required for a diagnostic counter.
        self._queue_full_drops = 0
        self._input_overflow_count = 0
        self.dropped_frames = 0  # sum of the two, set by stop()
        self.device_api: Optional[str] = None  # host API of the open stream, e.g. "mme"/"wasapi"
        self._last_device_name = "?"

        # Stage 1 capture path. capture_rate is the rate frames actually arrive
        # at; sample_rate stays the rate the backends receive (16 kHz), so the
        # resample happens once in stop(). capture_fallback_reason is set when
        # WASAPI was requested but could not be opened (UI shows it).
        self.capture_wasapi_requested = bool(capture_wasapi)
        self.capture_rate = sample_rate
        self.capture_fallback_reason: Optional[str] = None
        self.last_resample_ms: Optional[float] = None
        self._resampler = StreamingResampler()
        self._preroll_max_for(sample_rate)
        self.last_rms_dbfs: float = DBFS_FLOOR
        self.last_peak_dbfs: float = DBFS_FLOOR

        # Auto-stop on silence
        self.auto_stop_enabled = False
        self.auto_stop_silence_sec = 2.0
        self.on_auto_stop: Optional[Callable[[], None]] = None
        self._silence_frames = 0
        self._silence_threshold = 0.01  # RMS below this = silence

        # Initialize WebRTC processor if enabled
        if self.webrtc_enabled:
            try:
                self._webrtc_processor = AudioProcessor(
                    auto_gain_dbfs=auto_gain_dbfs,
                    noise_suppression_level=self.noise_suppression_level,
                )
            except Exception:
                self._webrtc_processor = None
                self.webrtc_enabled = False

    # ------------------------------------------------------------------ #
    # Persistent stream lifecycle                                         #
    # ------------------------------------------------------------------ #

    def open_stream(self) -> bool:
        """Open the persistent input stream. May block 25+ seconds on a
        degraded audio stack — call from a background thread only."""
        if not AUDIO_AVAILABLE:
            logger.error("AUDIO_LIBS_NOT_AVAILABLE")
            return False
        with self._stream_lock:
            if self._closed:
                return False
            if self.stream_alive():
                return True

            # Never construct a replacement over a still-open dead stream
            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None
                self._stream_ok = False

            device_param = self._resolve_device()
            t0 = time.monotonic()

            # Stage 1: WASAPI @48 kHz first when requested, MME @16 kHz as the
            # visible fallback (D3). Flag off -> only the legacy attempt runs.
            attempts = []
            if self.capture_wasapi_requested:
                wasapi_dev = self._wasapi_input_device()
                if wasapi_dev is None:
                    self.capture_fallback_reason = "no WASAPI input endpoint"
                    self._fallback_since = time.monotonic()
                else:
                    attempts.append((wasapi_dev, self.WASAPI_RATE, self.WASAPI_BLOCKSIZE))
            attempts.append((device_param, self.sample_rate, 1024))

            stream = None
            open_rate = self.sample_rate
            open_device = device_param
            for idx, (dev, rate, blocksize) in enumerate(attempts):
                is_last = idx == len(attempts) - 1
                # The WASAPI attempt gets one retry after a settle second:
                # PortAudioError -9992 "Insufficient memory" is transient, and
                # without the retry a single hiccup pinned the app to MME for
                # 7 h 40 min / 30 recordings (2026-09-02).
                tries = 1 if is_last else 2
                last_exc = None
                for attempt_no in range(tries):
                    if attempt_no:
                        logger.warning("AUDIO_OPEN_RETRY | rate=%d", rate)
                        time.sleep(self.OPEN_RETRY_DELAY_S)
                    try:
                        stream = self._construct_stream(dev, rate, blocksize)
                    except Exception as e:
                        stream, last_exc = None, e
                        logger.error("AUDIO_OPEN_FAILED | rate=%d | %s: %s",
                                     rate, type(e).__name__, e)
                        continue
                    if stream is None:
                        return False  # quit began during the constructor
                    open_rate = rate
                    open_device = dev
                    break
                if stream is not None:
                    break
                if not is_last:
                    self.capture_fallback_reason = (
                        f"{type(last_exc).__name__}: {last_exc}" if last_exc else "unknown")
                    self._fallback_since = time.monotonic()
                    log_event("capture_fallback", requested_rate=rate,
                              reason=type(last_exc).__name__ if last_exc else "unknown")
            if stream is None:
                self._stream_ok = False
                return False

            self._activate_stream(stream, open_rate, open_device)
            logger.info("AUDIO_OPEN | device=%s | api=%s | rate=%d | %.1fs",
                        self._last_device_name, self.device_api, self.capture_rate,
                        time.monotonic() - t0)
            log_event("capture_open", device_api=self.device_api,
                      capture_rate=self.capture_rate,
                      fallback_reason=self.capture_fallback_reason,
                      elapsed_s=round(time.monotonic() - t0, 3))
            return True

    def _construct_stream(self, dev, rate, blocksize):
        """Build and start one PortAudio input stream. Raises on failure.

        Returns None (after closing the stream) if the app started quitting
        during the constructor, which can block for 25 s on a degraded stack.
        """
        token = self._stream_token + 1

        def _finished():
            # A retiring stream fires this while its replacement is already
            # live — only the current stream may clear the ok flag.
            if self._stream_token == token:
                self._stream_ok = False

        stream = sd.InputStream(
            samplerate=rate,
            channels=self.channels,
            dtype=np.float32,
            callback=self._audio_callback,
            finished_callback=_finished,
            blocksize=blocksize,
            device=dev,
        )
        if self._closed:
            try:
                stream.close()
            except Exception:
                pass
            return None
        stream.start()
        stream._tk_token = token
        return stream

    def _activate_stream(self, stream, open_rate, open_device, state_locked=False):
        """Make `stream` the live stream. Caller holds _stream_lock."""
        self.capture_rate = open_rate
        self._preroll_max_for(open_rate, state_locked=state_locked)
        self._stream_token = getattr(stream, "_tk_token", self._stream_token + 1)
        self._stream = stream
        self._stream_ok = True
        self._stream_opened_at = time.monotonic()
        self._last_callback_ts = self._stream_opened_at
        try:
            # Must describe the device ACTUALLY opened, not the configured
            # one: on the WASAPI attempt they differ, and device_api is the
            # field burn-in uses to tell the two capture paths apart.
            dev_info = (sd.query_devices(open_device) if open_device is not None
                        else sd.query_devices(kind="input"))
            self._last_device_name = dev_info["name"]
            self.device_api = sd.query_hostapis(dev_info["hostapi"])["name"].lower()
        except Exception:
            self._last_device_name = "?"
            self.device_api = None

    @staticmethod
    def _discard_stream(stream):
        """Stop and close a stream, swallowing everything. May block ~14 s."""
        if stream is None:
            return
        try:
            stream.stop()
            stream.close()
        except Exception:
            pass

    def switch_device(self, name: str, hostapi: str) -> bool:
        """Point the recorder at another input device and reopen the stream.

        Used by the first-run dialog and Settings. Refuses mid-recording; may
        block as long as any other open (call from a background thread).
        """
        if not AUDIO_AVAILABLE or self._closed or self._recording:
            return False
        with self._stream_lock:
            if self._closed or self._recording:
                return False
            old, self._stream = self._stream, None
            self._stream_ok = False
            self.device_name = name or ""
            self.device_hostapi = hostapi or ""
            self.device = -1          # a name always wins over the legacy index
            self._discard_stream(old)
        return self.open_stream()

    @staticmethod
    def list_input_devices():
        """[(index, name, hostapi_name)] for every input-capable device."""
        out = []
        if not AUDIO_AVAILABLE:
            return out
        try:
            for idx, info in enumerate(sd.query_devices()):
                if info.get("max_input_channels", 0) < 1:
                    continue
                try:
                    api = sd.query_hostapis(info["hostapi"])["name"]
                except Exception:
                    api = "?"
                out.append((idx, info.get("name", "?"), api))
        except Exception as e:
            logger.warning("DEVICE_ENUM_FAILED | %s: %s", type(e).__name__, e)
        return out

    def recovery_idle_deficit_s(self) -> float:
        """Seconds still to wait before a recovery probe may run (0 = now)."""
        return max(0.0, self.RECOVER_IDLE_GRACE_S - (time.monotonic() - self._last_stop_ts))

    def try_recover_wasapi(self) -> bool:
        """Try to get back onto WASAPI after a fallback to MME.

        The live MME stream is NEVER closed until a WASAPI replacement is
        already open and started — a failed attempt must not cost the owner a
        single dictation. Returns True only when the swap happened.

        The only stream-lifecycle entry point besides open_stream() and
        close_stream(); like them, it may block for tens of seconds and must
        be called from a background thread.
        """
        if not AUDIO_AVAILABLE or self._closed:
            return False
        if not self.capture_wasapi_requested or not self.capture_fallback_reason:
            return False
        if self._recording:
            return False
        if self.recovery_idle_deficit_s() > 0:
            return False

        wasapi_dev = self._wasapi_input_device()
        if wasapi_dev is None:
            logger.info("RECOVER_SKIP | no WASAPI input endpoint")
            return False

        with self._stream_lock:
            if self._closed or self._recording or not self.capture_fallback_reason:
                return False
            old = self._stream
            self._recovering = True
            t0 = time.monotonic()
            try:
                # Strategy PROBE_THEN_SWAP: PortAudio allows a shared-mode
                # WASAPI stream alongside the live MME one, so the candidate is
                # opened first and the MME stream only dies once it is running.
                logger.info("RECOVER_STRATEGY | probe_then_swap")
                try:
                    candidate = self._construct_stream(
                        wasapi_dev, self.WASAPI_RATE, self.WASAPI_BLOCKSIZE)
                except Exception as e:
                    logger.warning("RECOVER_FAILED | %s: %s", type(e).__name__, e)
                    log_event("capture_recover_failed", reason=type(e).__name__)
                    return False
                if candidate is None:
                    return False

                # A hotkey may have started a recording while the candidate was
                # opening (that open is not instant). Re-check under the lock
                # the callback uses, so the swap can never land mid-recording.
                with self._state_lock:
                    busy = self._recording
                    if not busy:
                        sticky_s = round(time.monotonic() - self._fallback_since, 1)
                        self._activate_stream(candidate, self.WASAPI_RATE, wasapi_dev,
                                              state_locked=True)
                        self.capture_fallback_reason = None
                if busy:
                    logger.info("RECOVER_DEFERRED | recording started during probe")
                    self._discard_stream(candidate)
                    return False

                self._discard_stream(old)
                logger.info("AUDIO_RECOVERED | device=%s | api=%s | rate=%d | "
                            "sticky=%.0fs | %.1fs",
                            self._last_device_name, self.device_api, self.capture_rate,
                            sticky_s, time.monotonic() - t0)
                log_event("capture_recovered", device_api=self.device_api,
                          capture_rate=self.capture_rate, sticky_s=sticky_s,
                          elapsed_s=round(time.monotonic() - t0, 3))
                return True
            finally:
                self._recovering = False

    def _preroll_max_for(self, rate: int, state_locked: bool = False) -> None:
        """Rescale the pre-roll ring to PREROLL_SEC at `rate` (0.4 s = 19 200
        samples @48 kHz). Frames captured at another rate are dropped.

        `state_locked=True` when the caller already holds _state_lock (the
        recovery swap does, and the lock is not reentrant).
        """
        new_max = int(self.PREROLL_SEC * rate)
        if new_max == self.PREROLL_MAX_SAMPLES:
            return
        self.PREROLL_MAX_SAMPLES = new_max
        if state_locked:
            self._preroll.clear()
            self._preroll_samples = 0
            return
        with self._state_lock:
            self._preroll.clear()
            self._preroll_samples = 0

    def _resolve_device(self) -> Optional[int]:
        """PortAudio index for the configured device, or None for the default.

        Preference order: stored host API + name (stable across reboots and
        re-plugs) -> legacy index from an old config (resolved once, then
        reported back as a name) -> system default. A configured device that
        is not present is NOT an error: fall back to the default and leave a
        message in device_warning for the status line.
        """
        self.device_warning = None
        if self.device_name:
            try:
                for idx, info in enumerate(sd.query_devices()):
                    if info.get("max_input_channels", 0) < 1:
                        continue
                    if info.get("name") != self.device_name:
                        continue
                    if self.device_hostapi:
                        api = sd.query_hostapis(info["hostapi"])["name"].lower()
                        if api != self.device_hostapi.lower():
                            continue
                    return idx
            except Exception as e:
                logger.warning("DEVICE_LOOKUP_FAILED | %s: %s", type(e).__name__, e)
            self.device_warning = (
                f"Микрофон «{self.device_name}» не найден — использую системный по умолчанию")
            logger.warning("DEVICE_NOT_FOUND | name=%s api=%s", self.device_name,
                           self.device_hostapi or "?")
            return None

        if self.device is not None and self.device != -1:
            # Legacy index: use it once, then remember what it pointed at.
            try:
                info = sd.query_devices(self.device)
                api = sd.query_hostapis(info["hostapi"])["name"].lower()
                self.device_name = info["name"]
                self.device_hostapi = api
                if self.on_device_resolved:
                    self.on_device_resolved(self.device_name, self.device_hostapi)
                logger.info("DEVICE_INDEX_RESOLVED | %d -> %s (%s)",
                            self.device, self.device_name, self.device_hostapi)
                return self.device
            except Exception as e:
                self.device_warning = (
                    "Сохранённый микрофон недоступен — использую системный по умолчанию")
                logger.warning("DEVICE_INDEX_STALE | index=%s | %s: %s",
                               self.device, type(e).__name__, e)
        return None

    @staticmethod
    def _wasapi_input_device() -> Optional[int]:
        """Default input endpoint of the WASAPI host API, or None if absent."""
        try:
            for api in sd.query_hostapis():
                if "wasapi" in api["name"].lower():
                    dev = api.get("default_input_device", -1)
                    return dev if dev is not None and dev >= 0 else None
        except Exception as e:
            logger.warning("WASAPI_ENUM_FAILED | %s: %s", type(e).__name__, e)
        return None

    def ensure_stream_async(self):
        """Warm up / re-open the stream in a background thread (idempotent)."""
        with self._open_flag_lock:
            if self._stream_opening or self._closed or self.stream_alive():
                return
            self._stream_opening = True

        def _opener():
            try:
                self.open_stream()
            finally:
                with self._open_flag_lock:
                    self._stream_opening = False

        threading.Thread(target=_opener, daemon=True, name="audio-open").start()

    def close_stream(self):
        """Permanent teardown on app quit. May block 14+ seconds — call from
        a daemon thread with a join budget."""
        self._closed = True
        with self._stream_lock:
            if self._stream is not None:
                t0 = time.monotonic()
                self._discard_stream(self._stream)
                self._stream = None
                logger.info("AUDIO_CLOSE | %.1fs", time.monotonic() - t0)
            self._stream_ok = False

    def stream_alive(self) -> bool:
        """Plain reads, no locks — safe from any thread."""
        stream = self._stream
        if stream is None or not self._stream_ok:
            return False
        try:
            if not stream.active:
                return False
        except Exception:
            return False
        # A stream can stall with active=True: no callbacks = dead.
        # Grace period right after open (callback hasn't fired yet).
        now = time.monotonic()
        if (now - self._stream_opened_at >= self.CALLBACK_STALL_SEC
                and now - self._last_callback_ts >= self.CALLBACK_STALL_SEC):
            return False
        return True

    # ------------------------------------------------------------------ #
    # Capture                                                             #
    # ------------------------------------------------------------------ #

    def _audio_callback(self, indata, frames, time_info, status):
        """PortAudio callback — deliberately minimal: stamp, copy, route.
        All processing (WebRTC, levels, quality) happens in the collector."""
        self._last_callback_ts = time.monotonic()
        if self._closed:
            return
        if status:
            logger.debug("AUDIO_STATUS | %s", status)
            if status.input_overflow:
                self._input_overflow_count += 1  # lock-free: cheap, approximate is fine

        data = indata.copy()
        with self._state_lock:
            if self._recording:
                try:
                    self._audio_queue.put_nowait(data)
                except queue.Full:
                    self._queue_full_drops += 1  # lock-free, same rationale
            else:
                self._preroll.append(data)
                self._preroll_samples += len(data)
                while (self._preroll_samples > self.PREROLL_MAX_SAMPLES
                        and len(self._preroll) > 1):
                    old = self._preroll.popleft()
                    self._preroll_samples -= len(old)

    def _apply_webrtc(self, data):
        """WebRTC NS/AGC over a float32 (n, 1) buffer AT 16 kHz.

        `webrtc_noise_gain` accepts only 10 ms of 16 kHz mono per call, so on
        the Stage-1 48 kHz capture path this cannot run per frame — it runs
        once in stop() over the resampled buffer instead. The maths is
        identical (same sequential 10 ms chunks), only the moment differs.
        """
        if self.webrtc_enabled and self._webrtc_processor is not None:
            try:
                # Convert float32 [-1, 1] to int16 PCM for WebRTC
                data_int16 = (data * 32767).astype(np.int16)

                # Process in 10ms chunks (160 samples @ 16kHz)
                # WebRTC requires exactly 10ms chunks at 16kHz
                chunk_size = 160  # 10ms @ 16kHz
                processed_chunks = []

                for i in range(0, len(data_int16), chunk_size):
                    chunk = data_int16[i:i + chunk_size]
                    if len(chunk) < chunk_size:
                        # Pad last chunk if needed
                        chunk = np.pad(chunk, (0, chunk_size - len(chunk)), mode='constant')

                    # Process 10ms chunk
                    result = self._webrtc_processor.Process10ms(chunk.tobytes())
                    if result.audio:
                        processed_chunks.append(np.frombuffer(result.audio, dtype=np.int16))

                if processed_chunks:
                    # Convert back to float32 and reshape
                    data_int16 = np.concatenate(processed_chunks)
                    data = data_int16.astype(np.float32) / 32767.0
                    data = data.reshape(-1, 1)  # Ensure (samples, channels) shape
            except Exception as e:
                # Fallback to original data if WebRTC fails
                logger.warning("WEBRTC_PROCESSING_FAILED | %s", e)
        return data

    def _process_frame(self, data):
        """Per-frame path in the collector thread: WebRTC (16 kHz capture only)
        + level/quality/auto-stop tracking. Returns float32 shape (n, 1).

        On the 48 kHz capture path the frame is passed through untouched and
        WebRTC is deferred to stop(); levels are then measured on raw audio
        (pre-AGC), which is why the meter reads lower there.
        """
        if self.capture_rate != self.sample_rate:
            # Stage 1: resample here, in the collector thread, so the cost
            # overlaps with recording instead of landing on stop() (a 5-minute
            # recording would otherwise add ~570 ms). In steady state 960 input
            # samples -> 320 output = exactly two WebRTC 10 ms chunks, so this
            # path mostly avoids the partial-chunk padding R10 measured (only
            # the first chunk is short, while the group delay primes).
            data = self._resampler.process(data)
            if len(data) == 0:
                return data
        data = self._apply_webrtc(data)

        # Calculate audio level for visualization (use cleaned audio)
        try:
            peak = float(np.abs(data).max())
            rms = float(np.sqrt(np.mean(data ** 2)))

            # Track audio quality
            if peak > self._clipping_threshold:
                self.clipping_detected = True
            if rms < self._low_signal_threshold:
                self._low_signal_frames += 1
                # ~2 sec of low signal (frames arrive ~15 times/sec at 16kHz/1024 samples)
                frames_per_sec = self.sample_rate / max(len(data), 1)
                if self._low_signal_frames > frames_per_sec * 2:
                    self.low_signal = True
            else:
                self._low_signal_frames = 0

            # Auto-stop on silence
            if self.auto_stop_enabled and self.on_auto_stop:
                if rms < self._silence_threshold:
                    self._silence_frames += 1
                    frames_per_sec = self.sample_rate / max(len(data), 1)
                    if self._silence_frames > frames_per_sec * self.auto_stop_silence_sec:
                        self.on_auto_stop()
                        self._silence_frames = 0  # Reset to avoid repeated triggers
                else:
                    self._silence_frames = 0

            if self.on_level_update:
                self.on_level_update(rms)
        except Exception:
            pass

        return data

    def start(self) -> str:
        """Gate frames into a new recording. Returns 'started' | 'warming' |
        'error'. Non-blocking: never opens the device, never takes
        _stream_lock — instant even while a 25s open runs in the background."""
        if not AUDIO_AVAILABLE:
            logger.error("AUDIO_LIBS_NOT_AVAILABLE")
            return "error"

        with self._lock:
            if self._recording:
                return "started"

            if not self.stream_alive():
                self.ensure_stream_async()
                logger.warning("MIC_WARMING | stream not ready, opening in background")
                return "warming"

            # Ensure previous collect thread is stopped
            if self._collect_thread is not None and self._collect_thread.is_alive():
                self._collect_thread.join(timeout=1.0)
            self._collect_thread = None

            # Fresh session buffers BEFORE the recording flag flips
            self._audio_data = []
            self._audio_queue = queue.Queue(maxsize=500)

            # Reset audio quality tracking
            self.clipping_detected = False
            self.low_signal = False
            self.capture_degraded = False
            self._low_signal_frames = 0
            self._silence_frames = 0
            self._queue_full_drops = 0
            self._input_overflow_count = 0

            # Atomic idle→recording handoff: every frame lands either in the
            # pre-roll (before the flip, snapshotted here) or in the fresh
            # queue (after the flip) — none lost, none leaked.
            resampling = self.capture_rate != self.sample_rate
            if resampling:
                self._resampler.reset()

            with self._state_lock:
                self._recording = True
                if self._preroll:
                    if resampling:
                        # Pre-roll frames are at the capture rate, so they must
                        # go through the same collector path as live frames —
                        # queued ahead of them, order preserved by _state_lock.
                        for frame in self._preroll:
                            try:
                                self._audio_queue.put_nowait(frame)
                            except queue.Full:
                                self._queue_full_drops += 1
                    else:
                        self._audio_data.extend(self._preroll)  # raw pre-roll first
                    self._preroll.clear()
                    self._preroll_samples = 0

            # Collector gets the CURRENT queue/list as args — a stale
            # collector that outlived its join can never touch a new session
            self._collect_thread = threading.Thread(
                target=self._collect_audio,
                args=(self._audio_queue, self._audio_data),
                daemon=True,
            )
            self._collect_thread.start()
            return "started"

    def _collect_audio(self, audio_queue, audio_data):
        """Drain the session queue, processing each frame. Sentinel (None)
        signals clean exit. Bound to ONE session via args."""
        while True:
            try:
                data = audio_queue.get(timeout=0.1)
                if data is None:
                    break  # Sentinel received — drain remaining and exit
                audio_data.append(self._process_frame(data))
            except queue.Empty:
                if not self._recording:
                    break  # Fallback: exit if recording stopped without sentinel
                continue
            except Exception:
                break  # Exit on any error
        # Drain remaining items after sentinel
        while not audio_queue.empty():
            try:
                data = audio_queue.get_nowait()
                if data is not None:
                    audio_data.append(self._process_frame(data))
            except queue.Empty:
                break

    def stop(self) -> Optional[np.ndarray]:
        """Stop gating and return the recorded audio. Does NOT close the
        stream. Bounded: ≤2s worst case (collector join), typically <50ms."""
        with self._lock:
            if not self._recording:
                return None

            if not self.stream_alive():
                self.capture_degraded = True
                logger.warning("CAPTURE_DEGRADED | stream died during recording session")
                log_event("capture_degraded", device_api=self.device_api)

            with self._state_lock:
                self._recording = False
            self._last_stop_ts = time.monotonic()  # idle grace for try_recover_wasapi
            # No producer can enqueue past this point (callback checks
            # _recording under the same lock) — sentinel is guaranteed last.
            try:
                self._audio_queue.put(None, timeout=1.0)
            except queue.Full:
                pass  # collector exits via the _recording=False fallback

            # Wait for collect thread (it drains the queue itself)
            if self._collect_thread is not None and self._collect_thread.is_alive():
                self._collect_thread.join(timeout=2.0)
            self._collect_thread = None

            # Stage 1: flush the streaming resampler's tail (a few hundred
            # samples — the per-frame work already happened during recording).
            if self.capture_rate != self.sample_rate:
                t_rs = time.monotonic()
                try:
                    tail = self._resampler.finalize()
                    if len(tail):
                        self._audio_data.append(self._apply_webrtc(tail.reshape(-1, 1)))
                except Exception as e:
                    logger.error("RESAMPLE_TAIL_FAILED | %s: %s", type(e).__name__, e)
                    log_event("resample_failed", capture_rate=self.capture_rate,
                              error=type(e).__name__)
                self.last_resample_ms = round((time.monotonic() - t_rs) * 1000, 1)

            if not self._audio_data:
                return None

            # Concatenate all audio data
            try:
                audio = np.concatenate(self._audio_data, axis=0)
            except ValueError:
                return None  # Empty or incompatible arrays

            # Apply software boost ONLY if WebRTC AGC is not available
            # WebRTC AGC handles gain adaptation automatically
            if not self.webrtc_enabled and self.mic_boost != 1.0:
                audio = audio * self.mic_boost
                # Clip to prevent distortion
                audio = np.clip(audio, -1.0, 1.0)

            self.last_rms_dbfs, self.last_peak_dbfs = self.audio_level_dbfs(audio)
            self.dropped_frames = self._queue_full_drops + self._input_overflow_count
            if self.dropped_frames:
                log_event(
                    "queue_drop",
                    queue_full_drops=self._queue_full_drops,
                    input_overflow=self._input_overflow_count,
                    device_api=self.device_api,
                )

            return audio

    @staticmethod
    def audio_level_dbfs(audio: np.ndarray) -> Tuple[float, float]:
        """RMS and peak level of a full recording, in dBFS. Clamped at
        DBFS_FLOOR instead of -inf so the value is always JSON-safe."""
        if audio is None or len(audio) == 0:
            return DBFS_FLOOR, DBFS_FLOOR
        samples = audio.astype(np.float64)
        rms = float(np.sqrt(np.mean(samples ** 2)))
        peak = float(np.abs(samples).max())
        rms_dbfs = 20 * math.log10(rms) if rms > 0 else DBFS_FLOOR
        peak_dbfs = 20 * math.log10(peak) if peak > 0 else DBFS_FLOOR
        return max(rms_dbfs, DBFS_FLOOR), max(peak_dbfs, DBFS_FLOOR)

    # ------------------------------------------------------------------ #
    # Utilities                                                           #
    # ------------------------------------------------------------------ #

    def save_to_file(self, audio: np.ndarray, filepath: Optional[Path] = None) -> Path:
        """Save audio data to a WAV file."""
        if filepath is None:
            fd, filepath = tempfile.mkstemp(suffix=".wav")
            import os
            os.close(fd)
            filepath = Path(filepath)

        sf.write(str(filepath), audio, self.sample_rate)
        return filepath

    def get_duration(self, audio: np.ndarray) -> float:
        """Get duration of audio in seconds."""
        return len(audio) / self.sample_rate

    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._recording

    @staticmethod
    def list_devices() -> list:
        """List available audio input devices."""
        if not AUDIO_AVAILABLE:
            return []
        try:
            devices = sd.query_devices()
            input_devices = []
            for i, device in enumerate(devices):
                if device['max_input_channels'] > 0:
                    input_devices.append({
                        'index': i,
                        'name': device['name'],
                        'channels': device['max_input_channels'],
                        'sample_rate': device['default_samplerate']
                    })
            return input_devices
        except Exception:
            return []
