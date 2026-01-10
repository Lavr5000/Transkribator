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
        on_level_update: Optional[Callable[[float], None]] = None
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.on_level_update = on_level_update

        self._recording = False
        self._audio_queue: queue.Queue = queue.Queue()
        self._audio_data: list = []
        self._stream: Optional[sd.InputStream] = None
        self._lock = threading.Lock()

    def _audio_callback(self, indata, frames, time_info, status):
        """Callback for audio stream."""
        if status:
            with open("debug.log", "a") as f:
                f.write(f"[DEBUG] Audio callback status: {status}\n")
            print(f"Audio status: {status}")

        # Copy audio data
        data = indata.copy()
        self._audio_queue.put(data)

        # Log occasionally
        if hasattr(self, '_callback_count'):
            self._callback_count += 1
        else:
            self._callback_count = 1

        if self._callback_count % 50 == 1:  # Log first time and every ~1 second
            with open("debug.log", "a") as f:
                f.write(f"[DEBUG] Audio callback #{self._callback_count}: frames={frames}, data_shape={data.shape}\n")

        # Calculate audio level for visualization
        if self.on_level_update:
            level = np.abs(data).mean()
            self.on_level_update(float(level))

    def start(self) -> bool:
        """Start recording audio."""
        with open("debug.log", "a") as f:
            f.write("[DEBUG] AudioRecorder.start() called\n")

        if not AUDIO_AVAILABLE:
            print("Audio libraries not available")
            with open("debug.log", "a") as f:
                f.write("[ERROR] Audio libraries not available\n")
            return False

        with self._lock:
            if self._recording:
                with open("debug.log", "a") as f:
                    f.write("[DEBUG] Already recording\n")
                return True

            try:
                self._audio_data = []
                self._audio_queue = queue.Queue()

                with open("debug.log", "a") as f:
                    f.write(f"[DEBUG] Creating InputStream: sample_rate={self.sample_rate}, channels={self.channels}\n")

                self._stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    dtype=np.float32,
                    callback=self._audio_callback,
                    blocksize=1024
                )

                with open("debug.log", "a") as f:
                    f.write("[DEBUG] Starting stream...\n")

                self._stream.start()

                with open("debug.log", "a") as f:
                    f.write("[DEBUG] Stream started, setting _recording=True\n")

                self._recording = True

                # Start thread to collect audio data
                self._collect_thread = threading.Thread(target=self._collect_audio)
                self._collect_thread.start()

                with open("debug.log", "a") as f:
                    f.write("[DEBUG] Collect thread started\n")

                return True
            except Exception as e:
                with open("debug.log", "a") as f:
                    f.write(f"[ERROR] Failed to start recording: {e}\n")
                    import traceback
                    f.write(f"[ERROR] Traceback: {traceback.format_exc()}\n")
                print(f"Failed to start recording: {e}")
                return False

    def _collect_audio(self):
        """Collect audio data from queue."""
        while self._recording:
            try:
                data = self._audio_queue.get(timeout=0.1)
                self._audio_data.append(data)
            except queue.Empty:
                continue

    def stop(self) -> Optional[np.ndarray]:
        """Stop recording and return audio data."""
        with open("debug.log", "a") as f:
            f.write(f"[DEBUG] AudioRecorder.stop() called, _recording={self._recording}\n")

        with self._lock:
            if not self._recording:
                with open("debug.log", "a") as f:
                    f.write("[DEBUG] Not recording, returning None\n")
                return None

            self._recording = False

            with open("debug.log", "a") as f:
                f.write("[DEBUG] Closing stream...\n")

            if self._stream:
                self._stream.stop()
                self._stream.close()
                self._stream = None

            # Wait for collect thread
            if hasattr(self, '_collect_thread'):
                with open("debug.log", "a") as f:
                    f.write("[DEBUG] Waiting for collect thread...\n")
                self._collect_thread.join(timeout=1.0)

            # Drain remaining queue
            with open("debug.log", "a") as f:
                f.write(f"[DEBUG] Draining queue, current chunks: {len(self._audio_data)}\n")

            while not self._audio_queue.empty():
                try:
                    self._audio_data.append(self._audio_queue.get_nowait())
                except queue.Empty:
                    break

            with open("debug.log", "a") as f:
                f.write(f"[DEBUG] After drain, total chunks: {len(self._audio_data)}\n")

            if not self._audio_data:
                with open("debug.log", "a") as f:
                    f.write("[DEBUG] No audio data collected, returning None\n")
                return None

            # Concatenate all audio data
            audio = np.concatenate(self._audio_data, axis=0)
            with open("debug.log", "a") as f:
                f.write(f"[DEBUG] Returning audio: shape={audio.shape}, duration={len(audio)/self.sample_rate:.2f}s\n")
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
