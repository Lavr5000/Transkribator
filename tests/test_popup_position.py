"""Regression tests for the popup-position crash (A1).

30 of the 38 crash reports collected 2026-03-26..2026-08-20 are the same line:

    AttributeError: 'NoneType' object has no attribute 'geometry'
    src/main_window.py  QApplication.screenAt(main_pos).geometry()

`screenAt()` returns None whenever the window's top-left corner is outside
every screen (dragged past the edge, screen unplugged, resolution change).
`primaryScreen()` can be None too — a session with no screens at all.

The method is exercised through a lightweight stub `self`, so no MainWindow
(and no model load) is needed; the assertion is on the real production line.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QApplication

from src import main_window as mw_mod


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv[:1])
    yield app


class _FakePopup:
    def __init__(self):
        self.moved_to = None
        self.timeout_ms = None
        self.header = None
        self.text = None

    def height(self):
        return 120

    def set_header(self, value):
        self.header = value

    def set_text(self, value):
        self.text = value

    def move(self, x, y):
        self.moved_to = (x, y)

    def show_with_timeout(self, ms):
        self.timeout_ms = ms

    def raise_(self):
        pass


class _FakeWindow:
    """Minimal stand-in for MainWindow for `_show_text_popup`."""

    def __init__(self, pos):
        self._pos = pos
        self._text_popup = _FakePopup()
        self._audio_quality_warning = ""

    def pos(self):
        return self._pos

    def height(self):
        return 200


def _call(pos):
    win = _FakeWindow(pos)
    mw_mod.MainWindow._show_text_popup(win, "текст диктовки")
    return win


def test_popup_far_outside_all_screens_does_not_raise(qapp):
    """screenAt() is None for a window dragged far off-screen — the crash case."""
    assert QApplication.screenAt(QPoint(-100000, -100000)) is None

    win = _call(QPoint(-100000, -100000))

    assert win._text_popup.moved_to is not None
    assert win._text_popup.moved_to[0] == -100000
    assert win._text_popup.timeout_ms == 5000


def test_popup_without_any_screen_does_not_raise(qapp, monkeypatch):
    """No screens at all (headless/RDP): both screenAt and primaryScreen are None."""
    monkeypatch.setattr(QApplication, "screenAt", staticmethod(lambda _p: None))
    monkeypatch.setattr(QApplication, "primaryScreen", staticmethod(lambda: None))

    win = _call(QPoint(300, 400))

    # Clamp skipped entirely -> popup goes straight above the window.
    assert win._text_popup.moved_to == (300, 400 - 120 - 10)


def test_popup_on_screen_still_clamps(qapp):
    """The normal path is unchanged: too close to the top -> flip below."""
    screen = QApplication.primaryScreen()
    if screen is None:
        pytest.skip("no screen available in this session")
    top = screen.geometry().top()

    win = _call(QPoint(screen.geometry().left() + 50, top + 10))

    # popup_y would be top+10-120-10 < top+50 -> placed below the window
    assert win._text_popup.moved_to[1] == top + 10 + 200 + 10
