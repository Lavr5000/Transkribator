"""First-run dialog (A5): the mic test must tell the truth.

The dialog is the whole self-setup on a machine that is not the author's, so
the three cases that matter are: a microphone that hears nothing must say so
rather than show empty text; a working one must show the level and the words;
and Cancel must leave the recorder idle, never half-recording.

The recorder and the transcription function are stubbed — no device, no model.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtWidgets import QApplication

from src.config import Config
from src.first_run_dialog import SILENCE_DBFS, FirstRunDialog


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication(sys.argv[:1])


class _FakeRecorder:
    """Same surface the dialog uses, and it records what was called."""

    def __init__(self, peak_dbfs=-20.0, audio_len=48000):
        self.device_name = ""
        self.device_hostapi = ""
        self.last_peak_dbfs = peak_dbfs
        self._audio_len = audio_len
        self.calls = []
        self.recording = False

    def list_input_devices(self):
        return [(0, "Микрофон (USB PnP Audio Device)", "MME"),
                (7, "Микрофон (USB PnP Audio Device)", "Windows WASAPI")]

    def switch_device(self, name, hostapi):
        self.calls.append(("switch_device", name, hostapi))
        self.device_name, self.device_hostapi = name, hostapi
        return True

    def stream_alive(self):
        return True

    def open_stream(self):
        self.calls.append(("open_stream",))
        return True

    def start(self):
        self.calls.append(("start",))
        self.recording = True
        return "started"

    def stop(self):
        self.calls.append(("stop",))
        self.recording = False
        return np.zeros((self._audio_len, 1), dtype=np.float32)


def _dialog(qapp, recorder, transcribe=lambda a: "проверка связи", tmp_path=None,
            monkeypatch=None):
    cfg = Config()
    if tmp_path is not None and monkeypatch is not None:
        monkeypatch.setattr(Config, "get_config_dir", classmethod(lambda cls: tmp_path))
    return FirstRunDialog(cfg, recorder, transcribe)


def _run_probe(dlg, recorder):
    """Drive the worker synchronously — no Qt event loop needed."""
    name, api = dlg.device_combo.currentData()
    results = []
    dlg._probe_done.connect(lambda p, t, e: results.append((p, t, e)))
    dlg._probe_worker(name, api)
    assert results, "the worker must always report back"
    dlg._on_probe_done(*results[0])
    return results[0]


def test_silence_says_there_is_no_signal(qapp, monkeypatch):
    """A dead microphone must be named as such, not shown as empty text."""
    rec = _FakeRecorder(peak_dbfs=-90.0)
    called = []
    dlg = _dialog(qapp, rec, transcribe=lambda a: called.append(a) or "не должно вызваться")
    dlg.PROBE_SECONDS = 0
    monkeypatch.setattr("src.first_run_dialog.PROBE_SECONDS", 0.01)

    peak, text, error = _run_probe(dlg, rec)

    assert error == ""
    assert peak <= SILENCE_DBFS
    assert not called, "no point transcribing silence"
    assert "Сигнала нет" in dlg.result_label.text()


def test_signal_shows_level_and_text(qapp, monkeypatch):
    rec = _FakeRecorder(peak_dbfs=-18.0)
    monkeypatch.setattr("src.first_run_dialog.PROBE_SECONDS", 0.01)
    dlg = _dialog(qapp, rec, transcribe=lambda a: "раз два три")

    peak, text, error = _run_probe(dlg, rec)

    assert error == "" and text == "раз два три"
    assert "-18" in dlg.result_label.text()
    assert "раз два три" in dlg.result_label.text()
    assert ("start",) in rec.calls and ("stop",) in rec.calls


def test_cancel_leaves_the_recorder_idle(qapp, monkeypatch):
    monkeypatch.setattr("src.first_run_dialog.PROBE_SECONDS", 5.0)
    rec = _FakeRecorder()
    dlg = _dialog(qapp, rec)
    dlg._cancelled = True          # as if Cancel was pressed before the probe

    _run_probe(dlg, rec)

    assert rec.recording is False
    assert ("start",) not in rec.calls, "a cancelled probe must not open a recording"
    assert "отменена" in dlg.result_label.text().lower()


def test_probe_uses_the_selected_device(qapp, monkeypatch):
    monkeypatch.setattr("src.first_run_dialog.PROBE_SECONDS", 0.01)
    rec = _FakeRecorder(peak_dbfs=-18.0)
    dlg = _dialog(qapp, rec)
    dlg.device_combo.setCurrentIndex(2)   # WASAPI entry

    _run_probe(dlg, rec)

    assert ("switch_device", "Микрофон (USB PnP Audio Device)", "Windows WASAPI") in rec.calls


def test_done_stores_the_device_by_name(qapp, tmp_path, monkeypatch):
    rec = _FakeRecorder()
    monkeypatch.setattr(Config, "get_config_dir", classmethod(lambda cls: tmp_path))
    cfg = Config()
    dlg = FirstRunDialog(cfg, rec, lambda a: "")
    dlg.device_combo.setCurrentIndex(1)   # MME entry

    dlg._finish()

    assert cfg.audio_device_name == "Микрофон (USB PnP Audio Device)"
    assert cfg.audio_hostapi == "MME"
    assert cfg.audio_device_legacy_index == -1
    assert cfg.first_run is False
