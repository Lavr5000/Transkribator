"""Audio recording module for WhisperTyping."""
import io
import logging
import queue
import threading
import tempfile
from pathlib import Path
from typing import Callable, Optional
import numpy as np

logger = logging.getLogger("transkribator")

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
    """Records audio from the microphone with WebRTC noise suppression and AGC.

    When webrtc_enabled=True (default):
    - WebRTC Noise Suppression removes background noise
    - WebRTC AGC normalizes audio to -3 dBFS target automatically
    - mic_boost parameter is ignored (AGC handles gain)

    When webrtc_enabled=False (fallback):
    - Raw audio capture with optional software mic_boost
    """

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
        self._shutting_down = False  # Flag to prevent callbacks during shutdown
        self._audio_queue: queue.Queue = queue.Queue(maxsize=500)
        self._audio_data: list = []
        self._stream: Optional[sd.InputStream] = None
        self._lock = threading.Lock()
        self._collect_thread: Optional[threading.Thread] = None

        # Audio quality tracking
        self.clipping_detected = False  # Peak > 0.95
        self.low_signal = False  # RMS < 0.005 for > 2 seconds
        self._low_signal_frames = 0  # Counter for consecutive low-signal frames
        self._low_signal_threshold = 0.005
        self._clipping_threshold = 0.95

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

    def _audio_callback(self, indata, frames, time_info, status):
        """Callback for audio stream - applies WebRTC noise suppression if enabled."""
        # Early exit if shutting down
        if self._shutting_down or not self._recording:
            return

        if status:
            logger.debug("AUDIO_STATUS | %s", status)

        # Copy audio data
        data = indata.copy()

        # Apply WebRTC processing if enabled (real-time noise suppression)
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

        try:
            self._audio_queue.put_nowait(data)
        except queue.Full:
            pass  # Drop frame if queue is full

        # Calculate audio level for visualization (use cleaned audio)
        try:
            peak = float(np.abs(data).max())
            rms = float(np.sqrt(np.mean(data ** 2)))

            # Track audio quality
            if peak > self._clipping_threshold:
                self.clipping_detected = True
            if rms < self._low_signal_threshold:
                self._low_signal_frames += 1
                # ~2 sec of low signal (callback fires ~100 times/sec at 16kHz/160 samples)
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

    def start(self) -> bool:
        """Start recording audio."""
        if not AUDIO_AVAILABLE:
            logger.error("AUDIO_LIBS_NOT_AVAILABLE")
            return False

        with self._lock:
            if self._recording:
                return True

            try:
                # Reset state - ALWAYS reset shutting_down flag
                # This ensures on_level_update callback works even after previous errors
                self._audio_data = []
                self._audio_queue = queue.Queue(maxsize=500)
                self._shutting_down = False

                # Reset audio quality tracking
                self.clipping_detected = False
                self.low_signal = False
                self._low_signal_frames = 0
                self._silence_frames = 0

                # Ensure previous collect thread is stopped
                if self._collect_thread is not None and self._collect_thread.is_alive():
                    self._collect_thread.join(timeout=1.0)
                self._collect_thread = None

                # Prepare device parameter (None = system default)
                device_param = None if self.device == -1 else self.device

                self._stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    dtype=np.float32,
                    callback=self._audio_callback,
                    blocksize=1024,
                    device=device_param
                )

                # IMPORTANT: set _recording and start collect thread BEFORE stream
                # to avoid race condition where first audio frames are dropped
                self._recording = True
                self._collect_thread = threading.Thread(target=self._collect_audio, daemon=True)
                self._collect_thread.start()
                self._stream.start()

                return True
            except Exception as e:
                logger.error("RECORDING_START_FAILED | %s", e)
                # Ensure shutting_down is reset even on error
                self._shutting_down = False
                return False

    def _collect_audio(self):
        """Collect audio data from queue. Sentinel (None) signals clean exit."""
        while True:
            try:
                data = self._audio_queue.get(timeout=0.1)
                if data is None:
                    break  # Sentinel received — drain remaining and exit
                self._audio_data.append(data)
            except queue.Empty:
                if not self._recording:
                    break  # Fallback: exit if recording stopped without sentinel
                continue
            except Exception:
                break  # Exit on any error
        # Drain remaining items after sentinel
        while not self._audio_queue.empty():
            try:
                data = self._audio_queue.get_nowait()
                if data is not None:
                    self._audio_data.append(data)
            except queue.Empty:
                break

    def stop(self) -> Optional[np.ndarray]:
        """Stop recording and return audio data."""
        with self._lock:
            if not self._recording:
                return None

            # Signal that we're stopping
            self._recording = False
            self._shutting_down = True

            # Stop the stream first to prevent more callbacks
            if self._stream:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass  # Ignore errors during cleanup
                self._stream = None

            # Signal collect thread to drain and exit
            self._audio_queue.put(None)

            # Wait for collect thread (it drains the queue itself)
            if self._collect_thread is not None and self._collect_thread.is_alive():
                self._collect_thread.join(timeout=2.0)
            self._collect_thread = None

            # Reset shutdown flag for next recording
            self._shutting_down = False

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

            return audio

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
