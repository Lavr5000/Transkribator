"""Stage-1 capture-path tests (PLAN.md Stage 1 / D3), device-free.

sounddevice is stubbed, so these run on any machine: they check the FLAG
SEMANTICS — 48 kHz WASAPI first, visible MME fallback, pre-roll rescaling,
resample-at-stop, deferred WebRTC — not the actual driver.
"""

import sys
import types
from unittest.mock import patch

import numpy as np
import pytest

from src import audio_recorder as ar_mod
from src.audio_recorder import AudioRecorder


class _FakeStream:
    def __init__(self, **kw):
        self.kw = kw
        self.active = True
        self.started = False

    def start(self):
        self.started = True

    def stop(self):
        self.active = False

    def close(self):
        self.active = False


def _fake_sd(open_ok, hostapis=None, devices=None):
    """Minimal sounddevice stand-in. `open_ok(rate)` decides which rates open."""
    opened = []

    def InputStream(**kw):
        opened.append(kw)
        if not open_ok(kw["samplerate"]):
            raise RuntimeError(f"cannot open at {kw['samplerate']} Hz")
        return _FakeStream(**kw)

    # Device 7 sits on host API 1 (WASAPI), everything else on host API 0 (MME),
    # so device_api can be checked against the device actually opened.
    def query_devices(dev=None, kind=None):
        if devices is not None:
            return devices
        return {"name": f"Fake Mic {dev}", "hostapi": 1 if dev == 7 else 0}

    sd = types.SimpleNamespace(
        InputStream=InputStream,
        opened=opened,
        query_hostapis=lambda index=None: (
            hostapis[index] if index is not None
            else (hostapis if hostapis is not None else [])
        ),
        query_devices=query_devices,
    )
    return sd


HOSTAPIS = [
    {"name": "MME", "default_input_device": 0},
    {"name": "Windows WASAPI", "default_input_device": 7},
]


@pytest.fixture
def rec_factory():
    made = []

    def make(**kw):
        r = AudioRecorder(**kw)
        made.append(r)
        return r

    yield make
    for r in made:
        r._closed = True


def test_flag_off_keeps_16k_mme_path(rec_factory):
    sd = _fake_sd(lambda rate: True, HOSTAPIS)
    rec = rec_factory(capture_wasapi=False, webrtc_enabled=False)
    with patch.object(ar_mod, "sd", sd), patch.object(ar_mod, "AUDIO_AVAILABLE", True):
        assert rec.open_stream() is True
    assert [k["samplerate"] for k in sd.opened] == [16000]
    assert rec.capture_rate == 16000
    assert rec.PREROLL_MAX_SAMPLES == 6400
    assert rec.capture_fallback_reason is None


def test_flag_on_opens_wasapi_48k_blocksize_960(rec_factory):
    sd = _fake_sd(lambda rate: True, HOSTAPIS)
    rec = rec_factory(capture_wasapi=True, webrtc_enabled=False)
    with patch.object(ar_mod, "sd", sd), patch.object(ar_mod, "AUDIO_AVAILABLE", True):
        assert rec.open_stream() is True
    assert sd.opened[0]["samplerate"] == 48000
    assert sd.opened[0]["blocksize"] == 960
    assert sd.opened[0]["device"] == 7          # WASAPI default input endpoint
    assert rec.capture_rate == 48000
    assert rec.PREROLL_MAX_SAMPLES == 19200     # 0.4 s @ 48 kHz (Stage 1 spec)
    assert rec.capture_fallback_reason is None
    # device_api must name the API actually opened, not the configured device.
    assert rec.device_api == "windows wasapi"


def test_wasapi_open_failure_falls_back_visibly(rec_factory):
    sd = _fake_sd(lambda rate: rate == 16000, HOSTAPIS)
    rec = rec_factory(capture_wasapi=True, webrtc_enabled=False)
    events = []
    with patch.object(ar_mod, "sd", sd), \
         patch.object(ar_mod, "AUDIO_AVAILABLE", True), \
         patch.object(ar_mod, "log_event", lambda ev, **kw: events.append((ev, kw))):
        assert rec.open_stream() is True
    assert [k["samplerate"] for k in sd.opened] == [48000, 16000]
    assert rec.capture_rate == 16000
    assert rec.device_api == "mme", "history must show the fallback API"
    assert rec.capture_fallback_reason, "fallback must not be silent"
    names = [e[0] for e in events]
    assert "capture_fallback" in names and "capture_open" in names


def test_no_wasapi_hostapi_falls_back(rec_factory):
    sd = _fake_sd(lambda rate: True, [HOSTAPIS[0]])
    rec = rec_factory(capture_wasapi=True, webrtc_enabled=False)
    with patch.object(ar_mod, "sd", sd), patch.object(ar_mod, "AUDIO_AVAILABLE", True):
        assert rec.open_stream() is True
    assert [k["samplerate"] for k in sd.opened] == [16000]
    assert rec.capture_rate == 16000
    assert rec.capture_fallback_reason == "no WASAPI input endpoint"


def test_all_opens_failing_reports_failure(rec_factory):
    sd = _fake_sd(lambda rate: False, HOSTAPIS)
    rec = rec_factory(capture_wasapi=True, webrtc_enabled=False)
    with patch.object(ar_mod, "sd", sd), patch.object(ar_mod, "AUDIO_AVAILABLE", True):
        assert rec.open_stream() is False


def _tone_48k(seconds, freq=440.0):
    n = int(48000 * seconds)
    t = np.arange(n, dtype=np.float64) / 48000
    return (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32).reshape(-1, 1)


def test_streaming_resample_over_frames_matches_block_form(rec_factory):
    """The 48 kHz path resamples per frame in the collector; the concatenated
    result must equal the offline block resample of the same input."""
    from src.resampler import resample_48k_to_16k

    rec = rec_factory(capture_wasapi=True, webrtc_enabled=False)
    rec.capture_rate = 48000
    src = _tone_48k(0.25)                       # 12000 samples @48k
    frames = [src[i:i + 960] for i in range(0, len(src), 960)]

    rec._recording = True
    rec._audio_data = [rec._process_frame(f) for f in frames]
    rec._audio_data = [c for c in rec._audio_data if len(c)]
    with patch.object(ar_mod, "sd", _fake_sd(lambda r: True, HOSTAPIS)), \
         patch.object(ar_mod, "AUDIO_AVAILABLE", True):
        audio = rec.stop()

    assert audio is not None and audio.shape[1] == 1
    expected = resample_48k_to_16k(src)
    assert audio.shape == expected.shape
    assert np.abs(audio - expected).max() == 0.0
    assert rec.last_resample_ms is not None
    # A 440 Hz tone must survive the trip at roughly its original level.
    rms = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))
    assert 0.5 / np.sqrt(2) * 0.9 < rms < 0.5 / np.sqrt(2) * 1.1


def test_stop_at_16k_does_not_resample(rec_factory):
    rec = rec_factory(capture_wasapi=False, webrtc_enabled=False)
    rec._recording = True
    frames = np.zeros((1024, 1), dtype=np.float32)
    rec._audio_data = [frames.copy() for _ in range(4)]
    with patch.object(ar_mod, "sd", _fake_sd(lambda r: True, HOSTAPIS)), \
         patch.object(ar_mod, "AUDIO_AVAILABLE", True):
        audio = rec.stop()
    assert audio is not None and len(audio) == 4096
    assert rec.last_resample_ms is None


def test_webrtc_sees_16k_chunks_on_48k_path(rec_factory):
    """WebRTC (16 kHz-only library) must be fed AFTER the resample. In steady
    state a 960-sample capture frame yields exactly 320 samples = two whole
    10 ms chunks (so R10's partial-chunk padding does not happen); only the
    first frame is short, because the filter's group delay is still priming."""
    rec = rec_factory(capture_wasapi=True, webrtc_enabled=False)
    rec.capture_rate = 48000
    calls = []
    rec._apply_webrtc = lambda d: (calls.append(len(d)), d)[1]

    for _ in range(3):
        rec._process_frame(_tone_48k(0.02))     # 960 samples each
    assert calls, "WebRTC must run on the resampled chunks"
    assert set(calls[1:]) == {320}, f"steady-state chunks wrong: {sorted(set(calls[1:]))}"
    assert calls[0] == 288, "first frame is short by the primed group delay"
    assert all(c % 160 == 0 for c in calls[1:]), "steady state = whole 10 ms multiples"


def test_webrtc_still_per_frame_at_16k(rec_factory):
    rec = rec_factory(capture_wasapi=False, webrtc_enabled=False)
    calls = []
    rec._apply_webrtc = lambda d: (calls.append(len(d)), d)[1]
    rec._process_frame(np.zeros((1024, 1), dtype=np.float32))
    assert calls == [1024]


def test_preroll_rescale_clears_stale_frames(rec_factory):
    rec = rec_factory(capture_wasapi=True, webrtc_enabled=False)
    rec._preroll.append(np.zeros((1024, 1), dtype=np.float32))
    rec._preroll_samples = 1024
    rec._preroll_max_for(48000)
    assert rec.PREROLL_MAX_SAMPLES == 19200
    assert len(rec._preroll) == 0 and rec._preroll_samples == 0, (
        "frames captured at the old rate must not leak into a 48 kHz recording"
    )


def test_config_flag_defaults_off():
    from src.config import Config
    assert Config().capture_wasapi is False
