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
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.on_level_update = on_level_update
        self.device = device
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

            device_param = None if self.device == -1 else self.device
            t0 = time.monotonic()

            # Stage 1: WASAPI @48 kHz first when requested, MME @16 kHz as the
            # visible fallback (D3). Flag off -> only the legacy attempt runs.
            attempts = []
            if self.capture_wasapi_requested:
                wasapi_dev = self._wasapi_input_device()
                if wasapi_dev is None:
                    self.capture_fallback_reason = "no WASAPI input endpoint"
                else:
                    attempts.append((wasapi_dev, self.WASAPI_RATE, self.WASAPI_BLOCKSIZE))
            attempts.append((device_param, self.sample_rate, 1024))

            stream = None
            open_rate = self.sample_rate
            open_device = device_param
            for idx, (dev, rate, blocksize) in enumerate(attempts):
                try:
                    stream = sd.InputStream(
                        samplerate=rate,
                        channels=self.channels,
                        dtype=np.float32,
                        callback=self._audio_callback,
                        finished_callback=self._on_stream_finished,
                        blocksize=blocksize,
                        device=dev,
                    )
                    # Quit may have begun during the (possibly 25s) constructor
                    if self._closed:
                        try:
                            stream.close()
                        except Exception:
                            pass
                        return False
                    stream.start()
                    open_rate = rate
                    open_device = dev
                    break
                except Exception as e:
                    stream = None
                    is_last = idx == len(attempts) - 1
                    logger.error("AUDIO_OPEN_FAILED | rate=%d | %s: %s",
                                 rate, type(e).__name__, e)
                    if not is_last:
                        self.capture_fallback_reason = f"{type(e).__name__}: {e}"
                        log_event("capture_fallback", requested_rate=rate,
                                  reason=type(e).__name__)
            if stream is None:
                self._stream_ok = False
                return False

            self.capture_rate = open_rate
            self._preroll_max_for(open_rate)
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
                dev_name = dev_info["name"]
                self.device_api = sd.query_hostapis(dev_info["hostapi"])["name"].lower()
            except Exception:
                dev_name = "?"
                self.device_api = None
            logger.info("AUDIO_OPEN | device=%s | api=%s | rate=%d | %.1fs",
                        dev_name, self.device_api, self.capture_rate, time.monotonic() - t0)
            log_event("capture_open", device_api=self.device_api,
                      capture_rate=self.capture_rate,
                      fallback_reason=self.capture_fallback_reason,
                      elapsed_s=round(time.monotonic() - t0, 3))
            return True

    def _preroll_max_for(self, rate: int) -> None:
        """Rescale the pre-roll ring to PREROLL_SEC at `rate` (0.4 s = 19 200
        samples @48 kHz). Frames captured at another rate are dropped."""
        new_max = int(self.PREROLL_SEC * rate)
        if new_max == self.PREROLL_MAX_SAMPLES:
            return
        self.PREROLL_MAX_SAMPLES = new_max
        with self._state_lock:
            self._preroll.clear()
            self._preroll_samples = 0

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
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass
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

    def _on_stream_finished(self):
        """sounddevice finished_callback — stream stopped/aborted."""
        self._stream_ok = False

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
