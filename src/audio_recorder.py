"""Audio recording module for WhisperTyping."""
import io
import queue
import threading
import tempfile
from pathlib import Path
from typing import Callable, Optional
import numpy as np

try:
    import sounddevice as sd
    import soundfile as sf
    AUDIO_AVAILABLE = True
except (ImportError, OSError):
    AUDIO_AVAILABLE = False


class AudioRecorder:
    """Records audio from the microphone."""

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        on_level_update: Optional[Callable[[float], None]] = None,
        device: Optional[int] = None,
        mic_boost: float = 1.0  # Software gain multiplier (1.0 = no boost, 10.0 = 10x boost)
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.on_level_update = on_level_update
        self.device = device
        self.mic_boost = mic_boost

        self._recording = False
        self._shutting_down = False  # Flag to prevent callbacks during shutdown
        self._audio_queue: queue.Queue = queue.Queue()
        self._audio_data: list = []
        self._stream: Optional[sd.InputStream] = None
        self._lock = threading.Lock()
        self._collect_thread: Optional[threading.Thread] = None

    def _audio_callback(self, indata, frames, time_info, status):
        """Callback for audio stream."""
        # Early exit if shutting down
        if self._shutting_down or not self._recording:
            return

        if status:
            print(f"Audio status: {status}")

        # Copy audio data
        data = indata.copy()
        try:
            self._audio_queue.put_nowait(data)
        except queue.Full:
            pass  # Drop frame if queue is full

        # Calculate audio level for visualization
        if self.on_level_update and not self._shutting_down:
            try:
                level = np.abs(data).mean()
                self.on_level_update(float(level))
            except Exception:
                pass  # Ignore errors in callback

    def start(self) -> bool:
        """Start recording audio."""
        if not AUDIO_AVAILABLE:
            print("Audio libraries not available")
            return False

        with self._lock:
            if self._recording:
                return True

            try:
                # Reset state
                self._audio_data = []
                self._audio_queue = queue.Queue()
                self._shutting_down = False

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
                self._stream.start()
                self._recording = True

                # Start thread to collect audio data
                self._collect_thread = threading.Thread(target=self._collect_audio, daemon=True)
                self._collect_thread.start()

                return True
            except Exception as e:
                print(f"Failed to start recording: {e}")
                self._shutting_down = False
                return False

    def _collect_audio(self):
        """Collect audio data from queue."""
        while self._recording and not self._shutting_down:
            try:
                data = self._audio_queue.get(timeout=0.1)
                if not self._shutting_down:
                    self._audio_data.append(data)
            except queue.Empty:
                continue
            except Exception:
                break  # Exit on any error

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

            # Wait for collect thread
            if self._collect_thread is not None and self._collect_thread.is_alive():
                self._collect_thread.join(timeout=2.0)
            self._collect_thread = None

            # Drain remaining queue
            while not self._audio_queue.empty():
                try:
                    self._audio_data.append(self._audio_queue.get_nowait())
                except queue.Empty:
                    break

            # Reset shutdown flag for next recording
            self._shutting_down = False

            if not self._audio_data:
                return None

            # Concatenate all audio data
            try:
                audio = np.concatenate(self._audio_data, axis=0)
            except ValueError:
                return None  # Empty or incompatible arrays

            # Apply software boost if needed
            if self.mic_boost != 1.0:
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
