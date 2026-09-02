"""Stage-1 capture-path tests (PLAN.md Stage 1 / D3), device-free.

sounddevice is stubbed, so these run on any machine: they check the FLAG
SEMANTICS — 48 kHz WASAPI first, visible MME fallback, pre-roll rescaling,
resample-at-stop, deferred WebRTC — not the actual driver.
"""

import sys
import threading
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


def _wait_for(pred, timeout=5.0):
    """Spin until `pred()` is true — no sleeps baked into the assertions."""
    deadline = ar_mod.time.monotonic() + timeout
    while ar_mod.time.monotonic() < deadline:
        if pred():
            return True
        ar_mod.time.sleep(0.005)
    raise AssertionError("condition not reached within timeout")


@pytest.fixture
def rec_factory():
    made = []

    def make(**kw):
        r = AudioRecorder(**kw)
        r.OPEN_RETRY_DELAY_S = 0.0   # keep the suite fast; production waits 1 s
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
    # A2: the WASAPI attempt is retried once before MME is accepted.
    assert [k["samplerate"] for k in sd.opened] == [48000, 48000, 16000]
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


# --------------------------------------------------------------------------- #
# A2 — the MME fallback must not be permanent (2026-09-02: 7 h 40 min stuck)   #
# --------------------------------------------------------------------------- #


def _mme_then_wasapi_sd(gate=None):
    """sounddevice stub where the 48 kHz open fails N times, then succeeds.

    `gate`, when given, is a threading.Event the 48 kHz constructor waits on —
    used to hold a recovery probe open while a recording starts.
    """
    state = {"wasapi_failures": 0}
    opened = []

    def InputStream(**kw):
        opened.append(kw)
        if kw["samplerate"] == 48000:
            if state["wasapi_failures"] > 0:
                state["wasapi_failures"] -= 1
                raise RuntimeError("PortAudioError -9992 Insufficient memory")
            if gate is not None:
                gate.wait(5.0)
        return _FakeStream(**kw)

    return types.SimpleNamespace(
        InputStream=InputStream,
        opened=opened,
        state=state,
        query_hostapis=lambda index=None: (
            HOSTAPIS[index] if index is not None else HOSTAPIS),
        query_devices=lambda dev=None, kind=None: {
            "name": f"Fake Mic {dev}", "hostapi": 1 if dev == 7 else 0},
    )


def _fallen_back_recorder(rec_factory, sd, events):
    """Open a recorder that failed onto MME, ready for a recovery attempt."""
    rec = rec_factory(capture_wasapi=True, webrtc_enabled=False)
    with patch.object(ar_mod, "sd", sd), \
         patch.object(ar_mod, "AUDIO_AVAILABLE", True), \
         patch.object(ar_mod, "log_event", lambda ev, **kw: events.append((ev, kw))):
        assert rec.open_stream() is True
    assert rec.device_api == "mme"
    assert rec.capture_fallback_reason
    rec._last_stop_ts = 0.0          # long idle: monotonic() is far past 0
    rec._fallback_since = ar_mod.time.monotonic() - 900
    return rec


def test_a_transient_wasapi_error_is_retried_not_a_fallback(rec_factory):
    """(a) First 48 kHz open throws, the retry succeeds -> no fallback at all."""
    sd = _mme_then_wasapi_sd()
    sd.state["wasapi_failures"] = 1
    rec = rec_factory(capture_wasapi=True, webrtc_enabled=False)
    events = []
    with patch.object(ar_mod, "sd", sd), \
         patch.object(ar_mod, "AUDIO_AVAILABLE", True), \
         patch.object(ar_mod, "log_event", lambda ev, **kw: events.append((ev, kw))):
        assert rec.open_stream() is True

    assert [k["samplerate"] for k in sd.opened] == [48000, 48000]
    assert rec.capture_rate == 48000
    assert rec.device_api == "windows wasapi"
    assert rec.capture_fallback_reason is None
    assert "capture_fallback" not in [e[0] for e in events]


def test_b_both_wasapi_attempts_failing_falls_back_with_reason(rec_factory):
    """(b) Retry exhausted -> MME, visible reason, capture_fallback event."""
    sd = _mme_then_wasapi_sd()
    sd.state["wasapi_failures"] = 99
    events = []
    rec = _fallen_back_recorder(rec_factory, sd, events)

    assert [k["samplerate"] for k in sd.opened] == [48000, 48000, 16000]
    assert "Insufficient memory" in rec.capture_fallback_reason
    assert "capture_fallback" in [e[0] for e in events]


def test_c_recovery_swaps_back_to_wasapi_and_reports_sticky(rec_factory):
    """(c) A later probe succeeds -> WASAPI live, capture_recovered + sticky_s."""
    sd = _mme_then_wasapi_sd()
    sd.state["wasapi_failures"] = 99
    events = []
    rec = _fallen_back_recorder(rec_factory, sd, events)
    mme_stream = rec._stream
    sd.state["wasapi_failures"] = 0
    events.clear()

    with patch.object(ar_mod, "sd", sd), \
         patch.object(ar_mod, "AUDIO_AVAILABLE", True), \
         patch.object(ar_mod, "log_event", lambda ev, **kw: events.append((ev, kw))):
        assert rec.try_recover_wasapi() is True

    assert rec.device_api == "windows wasapi"
    assert rec.capture_rate == 48000
    assert rec.capture_fallback_reason is None
    assert rec._stream is not mme_stream
    assert mme_stream.active is False, "the MME stream must be closed after the swap"
    recovered = [kw for ev, kw in events if ev == "capture_recovered"]
    assert recovered and recovered[0]["sticky_s"] >= 900
    # The retired MME stream's finished_callback must not kill the new stream.
    assert rec._stream_ok is True


def test_d_failed_probe_leaves_the_mme_stream_untouched(rec_factory):
    """(d) Probe fails -> same MME stream object, still alive, still on MME."""
    sd = _mme_then_wasapi_sd()
    sd.state["wasapi_failures"] = 99
    events = []
    rec = _fallen_back_recorder(rec_factory, sd, events)
    mme_stream = rec._stream
    events.clear()

    with patch.object(ar_mod, "sd", sd), \
         patch.object(ar_mod, "AUDIO_AVAILABLE", True), \
         patch.object(ar_mod, "log_event", lambda ev, **kw: events.append((ev, kw))):
        assert rec.try_recover_wasapi() is False

    assert rec._stream is mme_stream and mme_stream.active is True
    assert rec.device_api == "mme"
    assert rec.capture_fallback_reason, "still on the fallback"
    assert "capture_recover_failed" in [e[0] for e in events]


def test_e_recovery_skipped_while_recording_or_too_soon(rec_factory):
    """(e) No probe during a recording, and none within the 60 s idle grace."""
    sd = _mme_then_wasapi_sd()
    sd.state["wasapi_failures"] = 99
    rec = _fallen_back_recorder(rec_factory, sd, [])
    sd.state["wasapi_failures"] = 0
    before = len(sd.opened)

    with patch.object(ar_mod, "sd", sd), patch.object(ar_mod, "AUDIO_AVAILABLE", True):
        rec._recording = True
        assert rec.try_recover_wasapi() is False
        rec._recording = False

        rec._last_stop_ts = ar_mod.time.monotonic() - 5     # 5 s < 60 s grace
        assert rec.try_recover_wasapi() is False

        rec._last_stop_ts = ar_mod.time.monotonic() - 120   # grace satisfied
        assert rec.try_recover_wasapi() is True

    assert len(sd.opened) == before + 1, "only the third call may touch the device"


def test_f_recording_started_during_probe_cancels_the_swap(rec_factory):
    """(f) A hotkey wins the race: candidate closed, MME kept, frames intact."""
    gate = threading.Event()
    sd = _mme_then_wasapi_sd(gate=gate)
    sd.state["wasapi_failures"] = 99
    rec = _fallen_back_recorder(rec_factory, sd, [])
    sd.state["wasapi_failures"] = 0
    mme_stream = rec._stream
    result = {}
    probes = len([k for k in sd.opened if k["samplerate"] == 48000])

    with patch.object(ar_mod, "sd", sd), patch.object(ar_mod, "AUDIO_AVAILABLE", True):
        t = threading.Thread(target=lambda: result.update(ok=rec.try_recover_wasapi()))
        t.start()
        # Wait until the probe is actually blocked inside the 48 kHz constructor,
        # so the race under test is the swap re-check, not the entry guard.
        _wait_for(lambda: len([k for k in sd.opened if k["samplerate"] == 48000]) > probes)
        assert rec.start() == "started"
        frame = np.full((1024, 1), 0.25, dtype=np.float32)
        rec._audio_callback(frame, 1024, None, None)
        gate.set()
        t.join(10)
        assert not t.is_alive()
        audio = rec.stop()

    assert result["ok"] is False, "the swap must be cancelled, not completed"
    assert rec._stream is mme_stream and mme_stream.active is True
    assert rec.capture_rate == 16000 and rec.device_api == "mme"
    assert audio is not None and len(audio) == 1024, "the recording lost no frames"


def test_g_start_during_recovery_is_immediate(rec_factory):
    """(g) start() never waits on _stream_lock while a probe holds it."""
    gate = threading.Event()
    sd = _mme_then_wasapi_sd(gate=gate)
    sd.state["wasapi_failures"] = 99
    rec = _fallen_back_recorder(rec_factory, sd, [])
    sd.state["wasapi_failures"] = 0
    probes = len([k for k in sd.opened if k["samplerate"] == 48000])

    with patch.object(ar_mod, "sd", sd), patch.object(ar_mod, "AUDIO_AVAILABLE", True):
        t = threading.Thread(target=rec.try_recover_wasapi)
        t.start()
        # _stream_lock is now held by the blocked probe.
        _wait_for(lambda: len([k for k in sd.opened if k["samplerate"] == 48000]) > probes)
        t0 = ar_mod.time.monotonic()
        status = rec.start()
        elapsed = ar_mod.time.monotonic() - t0
        gate.set()
        t.join(10)
        rec.stop()

    assert status == "started", "dictation must use the live MME stream at once"
    assert elapsed < 0.5, f"start() waited {elapsed:.2f}s on the recovery probe"


def test_recovery_backoff_is_10_20_40_60_capped():
    """(d, timer half) Failures widen the retry interval; success resets it."""
    from src.main_window import MainWindow

    assert [MainWindow._recovery_interval_ms(i) // 60_000 for i in range(6)] == \
        [10, 20, 40, 60, 60, 60]

    class _Stub:
        _recovery_running = True
        _recovery_step = 0
        armed = 0
        RECOVERY_BACKOFF_MIN = MainWindow.RECOVERY_BACKOFF_MIN

        def _arm_recovery_if_needed(self):
            self.armed += 1

    stub = _Stub()
    for expected in (1, 2, 3, 3, 3):
        MainWindow._on_recovery_finished(stub, False)
        assert stub._recovery_step == expected
    assert stub.armed == 5, "a failed probe must re-arm the timer"

    MainWindow._on_recovery_finished(stub, True)
    assert stub._recovery_step == 0, "a successful recovery resets the backoff"
    assert stub.armed == 5, "success must not re-arm"
