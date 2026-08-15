"""research_mode enforcement (Этап 0, item 5 / r1-30).

Integration test: drives success, Groq-fallback, cancellation, timeout,
exception and retry paths through the REAL MainWindow._done/_error/
_retry_transcription methods, with the paste and clipboard adapters
replaced by call-tracking stubs. With research_mode on, none of them may
ever be invoked, regardless of outcome.

MainWindow.__init__ is never called here on purpose: it opens a real audio
device, registers real OS-level global hotkeys, and may load a real model —
none of that is safe or necessary to exercise the paste/clipboard gate,
which lives entirely in _done()/_error()/_retry_transcription(). A minimal
instance is built with __new__ and only the attributes those three methods
actually touch.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src import main_window as mw_mod
from src import hotkeys as hotkeys_mod
from src.config import Config
from src.history_manager import HistoryManager


class _StubWidget:
    """No-op stand-in for the QLabel/QPushButton calls _done()/_error() make."""
    def __getattr__(self, name):
        return lambda *a, **k: None


class FakeSignal:
    """pyqtSignal stand-in: synchronous, no Qt event loop required."""
    def __init__(self):
        self._cb = None

    def connect(self, cb):
        self._cb = cb

    def disconnect(self):
        self._cb = None

    def emit(self, *args):
        if self._cb:
            self._cb(*args)


class FakeHybridThread:
    """Synchronous stand-in for HybridTranscriptionThread — exercises the
    real _retry_transcription() wiring without real QThread/event-loop
    machinery."""
    def __init__(self, remote_client, transcriber, audio, sample_rate, enable_remote=False):
        self.transcriber = transcriber
        self.audio = audio
        self.sample_rate = sample_rate
        self.transcription_done = FakeSignal()
        self.transcription_error = FakeSignal()
        self.finished = FakeSignal()

    def start(self):
        try:
            text, duration = self.transcriber.transcribe(self.audio, self.sample_rate)
            self.transcription_done.emit(text, duration, False)
        except Exception as e:
            self.transcription_error.emit(str(e))
        self.finished.emit()

    def cancel(self):
        pass

    def isRunning(self):
        return False

    def wait(self, timeout_ms=0):
        return True

    def deleteLater(self):
        pass


class FakeTranscriber:
    def __init__(self, behavior="success"):
        self.behavior = behavior
        self.last_used_fallback = False
        self.last_fallback_reason = None
        self.last_prompt_sent = None

    def transcribe(self, audio, sample_rate):
        if self.behavior == "success":
            return "успешный текст", 0.4
        if self.behavior == "fallback":
            self.last_used_fallback = True
            self.last_fallback_reason = "APIConnectionError"
            return "текст из sherpa-фолбэка", 0.9
        if self.behavior == "cancel":
            return "", 0.0
        if self.behavior == "exception":
            raise RuntimeError("Local transcription timeout")
        raise AssertionError(f"unknown behavior {self.behavior}")


class FakeRecorder:
    clipping_detected = False
    low_signal = False
    capture_degraded = False
    last_rms_dbfs = -40.0
    last_peak_dbfs = -20.0
    dropped_frames = 0
    device_api = "mme"

    def get_duration(self, audio):
        return len(audio) / 16000


def _make_window(tmp_path, monkeypatch, paste_calls, clipboard_calls, research_mode=True):
    monkeypatch.setattr(Config, "get_config_path", classmethod(lambda cls: tmp_path / "config.json"))
    monkeypatch.setattr(mw_mod, "type_text", lambda text, **k: paste_calls.append(("type", text)))
    monkeypatch.setattr(mw_mod, "safe_paste_text", lambda text, **k: paste_calls.append(("paste", text)))
    monkeypatch.setattr(mw_mod, "pyperclip", MagicMock(copy=lambda text: clipboard_calls.append(text)))
    monkeypatch.setattr(mw_mod, "CLIPBOARD_AVAILABLE", True)
    monkeypatch.setattr(mw_mod, "HybridTranscriptionThread", FakeHybridThread)
    monkeypatch.setattr(mw_mod, "QTimer", MagicMock(singleShot=lambda ms, cb: cb()))

    window = mw_mod.MainWindow.__new__(mw_mod.MainWindow)
    window.config = Config()
    window.config.research_mode = research_mode
    window.config.auto_copy = True
    window.config.auto_paste = True
    window.config.sample_rate = 16000
    hotkeys_mod.RESEARCH_MODE_BLOCK = research_mode

    window.recorder = FakeRecorder()
    window.transcriber = FakeTranscriber("success")
    window.history_manager = HistoryManager.__new__(HistoryManager)
    window.history_manager.max_entries = 50
    window.history_manager._history = []
    window.history_manager._history_file = tmp_path / "history.json"
    window._quality_monitor = MagicMock()
    window._settings = None
    window._shutting_down = False
    window._processing = False
    window._recording = False
    window._hover = False
    window._rec_duration = 0.5
    window._rec_start = 0.0
    window._transcription_start = 0.0
    window._trigger_id = "test-trigger"
    window._last_audio = np.zeros(8000, dtype=np.float32)
    window._thread = None
    window.remote_client = None
    window.vad_level_bar = None
    window._show_text_popup = lambda text: None    # real impl needs a live QWidget geometry
    window._show_error_popup = lambda message: None

    for attr in ("status_label", "timer_label", "mode_label", "cancel_btn",
                 "close_btn", "hotkey_label", "record_btn", "tray_rec", "_text_popup"):
        setattr(window, attr, _StubWidget())

    return window


@pytest.mark.parametrize("behavior,is_remote", [
    ("success", False),
    ("fallback", False),
    ("cancel", False),
])
def test_research_mode_blocks_done_paths(tmp_path, monkeypatch, behavior, is_remote):
    """success / Groq-fallback / cancellation all funnel through _done()."""
    paste_calls, clipboard_calls = [], []
    window = _make_window(tmp_path, monkeypatch, paste_calls, clipboard_calls)
    window.transcriber = FakeTranscriber(behavior)
    text, duration = window.transcriber.transcribe(window._last_audio, 16000)

    window._done(text, duration, is_remote=is_remote)

    assert paste_calls == []
    assert clipboard_calls == []


@pytest.mark.parametrize("message", [
    "Local transcription timeout",
    "ConnectionError: network unreachable",
])
def test_research_mode_blocks_error_paths(tmp_path, monkeypatch, message):
    """timeout / exception funnel through _error() — which never touches
    paste/clipboard regardless, but the test proves that stays true."""
    paste_calls, clipboard_calls = [], []
    window = _make_window(tmp_path, monkeypatch, paste_calls, clipboard_calls)

    window._error(message)

    assert paste_calls == []
    assert clipboard_calls == []


def test_research_mode_blocks_retry_path(tmp_path, monkeypatch):
    """retry re-enters through a real (faked-QThread) HybridTranscriptionThread,
    landing back in the same _done() gate."""
    paste_calls, clipboard_calls = [], []
    window = _make_window(tmp_path, monkeypatch, paste_calls, clipboard_calls)
    window.transcriber = FakeTranscriber("success")

    window._retry_transcription()

    assert paste_calls == []
    assert clipboard_calls == []


def test_stubs_actually_fire_without_research_mode(tmp_path, monkeypatch):
    """Guards against a vacuously-passing suite: with research_mode OFF,
    the auto-copy/auto-paste stubs MUST be hit for a normal success result —
    proving the tests above are actually exercising the gate, not a dead path."""
    paste_calls, clipboard_calls = [], []
    window = _make_window(tmp_path, monkeypatch, paste_calls, clipboard_calls, research_mode=False)

    window._done("текст", 0.4, is_remote=False)

    assert paste_calls != [] or clipboard_calls != []


def test_hotkeys_adapters_hard_blocked_at_module_flag(monkeypatch):
    """Defense-in-depth (r1-30): the adapters themselves refuse when
    RESEARCH_MODE_BLOCK is set, independent of any caller-side check."""
    calls = []
    monkeypatch.setattr(hotkeys_mod, "HOTKEY_BACKEND", "pynput")
    monkeypatch.setattr(hotkeys_mod, "paste_from_clipboard", lambda *a, **k: calls.append("paste") or True)
    original = hotkeys_mod.RESEARCH_MODE_BLOCK
    try:
        hotkeys_mod.RESEARCH_MODE_BLOCK = True
        hotkeys_mod.type_text("secret")
        result = hotkeys_mod.safe_paste_text("secret")
        assert calls == []
        assert result is False
    finally:
        hotkeys_mod.RESEARCH_MODE_BLOCK = original
