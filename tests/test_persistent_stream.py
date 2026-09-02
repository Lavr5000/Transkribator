"""Tests for the persistent-stream AudioRecorder (plan: transkribator-persistent-stream)."""
import sys
import time
import threading
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src import audio_recorder as ar_mod
from src.audio_recorder import AudioRecorder


class FakeStream:
    """Minimal stand-in for sd.InputStream."""

    open_delay = 0.0  # class-level: constructor sleep to simulate WASAPI stall

    def __init__(self, **kwargs):
        if FakeStream.open_delay:
            time.sleep(FakeStream.open_delay)
        self.kwargs = kwargs
        self.active = False

    def start(self):
        self.active = True

    def stop(self):
        self.active = False

    def close(self):
        self.active = False


class FakeSD:
    InputStream = FakeStream

    @staticmethod
    def query_devices(device=None, kind=None):
        return {"name": "Fake Mic"}


@pytest.fixture
def recorder(monkeypatch):
    monkeypatch.setattr(ar_mod, "sd", FakeSD)
    monkeypatch.setattr(ar_mod, "AUDIO_AVAILABLE", True)
    # Этап 0: open_stream() logs a text-free event on every successful open —
    # must not pollute the real app's event log (and burn-in numbers) with
    # fake-stream opens from the test suite.
    monkeypatch.setattr(ar_mod, "log_event", lambda *a, **k: None)
    FakeStream.open_delay = 0.0
    rec = AudioRecorder(sample_rate=16000, channels=1, webrtc_enabled=False)
    yield rec
    rec.close_stream()


def frame(value, n=1024):
    return np.full((n, 1), value, dtype=np.float32)


def feed(rec, value, n=1024):
    rec._audio_callback(frame(value, n), n, None, None)


def test_warming_when_stream_dead_single_opener(recorder, monkeypatch):
    """start() returns 'warming' and spawns exactly one opener thread."""
    opens = []
    orig = recorder.open_stream

    def counting_open():
        opens.append(1)
        time.sleep(0.3)
        return orig()

    monkeypatch.setattr(recorder, "open_stream", counting_open)
    assert recorder.start() == "warming"
    assert recorder.start() == "warming"  # second rapid press
    time.sleep(0.6)
    assert len(opens) == 1


def test_start_nonblocking_while_open_sleeps(recorder):
    """start() returns within 100ms while a 5s open runs in background."""
    FakeStream.open_delay = 5.0
    t0 = time.monotonic()
    result = recorder.start()
    elapsed = time.monotonic() - t0
    assert result == "warming"
    assert elapsed < 0.1
    FakeStream.open_delay = 0.0  # don't leave the class dirty


def test_preroll_ordering_no_loss_no_dup(recorder):
    """Idle frames land in pre-roll and precede recorded frames, in order."""
    assert recorder.open_stream() is True
    feed(recorder, 1.0, 100)  # idle → preroll
    feed(recorder, 2.0, 100)
    assert recorder.start() == "started"
    feed(recorder, 3.0, 100)  # recording → queue
    feed(recorder, 4.0, 100)
    time.sleep(0.3)  # let collector drain
    audio = recorder.stop()
    assert audio is not None
    assert audio.shape == (400, 1)
    assert audio.dtype == np.float32
    expected = np.concatenate([frame(v, 100) for v in (1.0, 2.0, 3.0, 4.0)], axis=0)
    assert np.array_equal(audio, expected)


def test_preroll_trimmed_by_sample_count(recorder):
    assert recorder.open_stream() is True
    for _ in range(20):  # 20 × 1024 = 20480 samples >> 6400 cap
        feed(recorder, 0.5)
    assert recorder._preroll_samples <= AudioRecorder.PREROLL_MAX_SAMPLES + 1024


def test_stop_does_not_close_stream_second_start_works(recorder):
    assert recorder.open_stream() is True
    stream = recorder._stream
    assert recorder.start() == "started"
    feed(recorder, 1.0)
    recorder.stop()
    assert recorder._stream is stream
    assert stream.active
    assert recorder.start() == "started"
    recorder.stop()


def test_close_stream_permanent(recorder):
    assert recorder.open_stream() is True
    recorder.close_stream()
    assert recorder._stream is None
    feed(recorder, 1.0)  # callback after close → ignored
    assert len(recorder._preroll) == 0
    assert recorder.open_stream() is False  # no reopen after permanent close


def test_quality_flags_reset_on_start(recorder):
    assert recorder.open_stream() is True
    recorder.clipping_detected = True
    recorder.low_signal = True
    recorder.capture_degraded = True
    assert recorder.start() == "started"
    assert not recorder.clipping_detected
    assert not recorder.low_signal
    assert not recorder.capture_degraded
    recorder.stop()


def test_degraded_capture_returns_partial_audio(recorder):
    assert recorder.open_stream() is True
    assert recorder.start() == "started"
    feed(recorder, 1.0)
    time.sleep(0.2)
    recorder._stream_ok = False  # simulate mid-session stream death
    audio = recorder.stop()
    assert audio is not None
    assert recorder.capture_degraded


def test_stalled_callback_reads_as_dead(recorder):
    assert recorder.open_stream() is True
    assert recorder.stream_alive()
    # Simulate: opened long ago, no callbacks since
    recorder._stream_opened_at = time.monotonic() - 10
    recorder._last_callback_ts = time.monotonic() - 10
    assert not recorder.stream_alive()
    assert recorder.start() == "warming"


def test_chunk_contract_float32_column(recorder):
    """Every chunk in _audio_data is float32 shape (n, 1)."""
    assert recorder.open_stream() is True
    feed(recorder, 1.0, 64)
    assert recorder.start() == "started"
    feed(recorder, 2.0, 128)
    time.sleep(0.3)
    with recorder._state_lock:
        chunks = list(recorder._audio_data)
    for c in chunks:
        assert c.dtype == np.float32
        assert c.ndim == 2 and c.shape[1] == 1
    recorder.stop()
