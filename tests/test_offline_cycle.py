"""Runtime half of the negative network gate (A3).

The import test proves nothing calls out at import time. This one blocks the
socket layer itself and drives the whole product path — capture, transcribe,
paste — through it. If anything in that path ever opens a connection, this
test raises instead of quietly degrading.
"""

import socket
import sys
import types
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import audio_recorder as ar_mod
from src import hotkeys as hotkeys_mod
from src.audio_recorder import AudioRecorder
from src.transcriber import Transcriber


class _NoNetwork(Exception):
    pass


@pytest.fixture
def network_blocked(monkeypatch):
    """Any attempt to construct a socket blows up loudly."""
    def _boom(*a, **kw):
        raise _NoNetwork("the product path must not open sockets")

    monkeypatch.setattr(socket, "socket", _boom)
    monkeypatch.setattr(socket, "create_connection", _boom)
    monkeypatch.setattr(socket, "getaddrinfo", _boom)
    return True


class _FakeStream:
    def __init__(self, **kw):
        self.kw = kw
        self.active = True

    def start(self):
        pass

    def stop(self):
        self.active = False

    def close(self):
        self.active = False


def _fake_sd():
    return types.SimpleNamespace(
        InputStream=lambda **kw: _FakeStream(**kw),
        query_hostapis=lambda index=None: (
            {"name": "MME", "default_input_device": 0} if index is not None else
            [{"name": "MME", "default_input_device": 0}]),
        query_devices=lambda dev=None, kind=None: {"name": "Fake Mic", "hostapi": 0},
    )


class _StubBackend:
    """Stands in for SherpaBackend: same contract, no model, no disk, no net."""

    def __init__(self, **kw):
        self.loaded = False

    def load_model(self):
        self.loaded = True
        return True

    def is_model_loaded(self):
        return self.loaded

    def unload_model(self):
        self.loaded = False

    def transcribe(self, audio, sample_rate=16000, cancel_event=None):
        assert len(audio) > 0, "the recorder handed the backend nothing"
        return "проверка офлайн цикла", 0.01


def test_record_transcribe_paste_never_opens_a_socket(network_blocked, monkeypatch):
    sd = _fake_sd()

    # 1. capture
    rec = AudioRecorder(capture_wasapi=False, webrtc_enabled=False)
    with patch.object(ar_mod, "sd", sd), patch.object(ar_mod, "AUDIO_AVAILABLE", True):
        assert rec.open_stream() is True
        assert rec.start() == "started"
        frame = np.full((1024, 1), 0.2, dtype=np.float32)
        for _ in range(4):
            rec._audio_callback(frame, 1024, None, None)
        audio = rec.stop()
        rec._closed = True
    assert audio is not None and len(audio) == 4096

    # 2. transcription
    monkeypatch.setattr("src.transcriber.get_backend", lambda name: _StubBackend)
    tr = Transcriber(backend="sherpa", model_size="giga-am-v3-ru-punct", language="ru",
                     enable_post_processing=False)
    text, elapsed = tr.transcribe(audio, 16000)
    assert text.strip(), "the stub backend produced no text"

    # 3. paste
    pasted = {}
    fake_clip = types.SimpleNamespace(copy=lambda t: pasted.setdefault("text", t))
    monkeypatch.setitem(sys.modules, "pyperclip", fake_clip)
    monkeypatch.setattr(hotkeys_mod, "HOTKEY_BACKEND", "keyboard", raising=False)
    monkeypatch.setattr(hotkeys_mod, "keyboard", types.SimpleNamespace(
        press=lambda k: None, release=lambda k: None), raising=False)
    monkeypatch.setattr(hotkeys_mod, "RESEARCH_MODE_BLOCK", False, raising=False)

    assert hotkeys_mod.safe_paste_text(text, delay_before_paste=0) is True
    assert pasted["text"] == text


def test_the_socket_block_is_real():
    """Negative control: with the fixture applied, a socket must raise."""
    with pytest.raises(_NoNetwork):
        with patch.object(socket, "socket", side_effect=_NoNetwork("blocked")):
            socket.socket()
