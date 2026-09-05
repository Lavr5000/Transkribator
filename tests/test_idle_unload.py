"""IdleUnloader: fires once after idle, defers while busy, cancel stops it."""
import threading
import time

from src.idle_unload import IdleUnloader


def _wait(pred, timeout=2.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if pred():
            return True
        time.sleep(0.01)
    return pred()


def test_fires_after_idle():
    calls = []
    u = IdleUnloader(0.05, lambda: calls.append(1), lambda: False)
    u.arm()
    assert _wait(lambda: len(calls) == 1)
    time.sleep(0.1)
    assert calls == [1], "must fire exactly once per arm"


def test_rearm_resets_countdown():
    calls = []
    u = IdleUnloader(0.15, lambda: calls.append(1), lambda: False)
    u.arm()
    time.sleep(0.1)
    u.arm()  # dictation happened again: countdown restarts
    time.sleep(0.1)
    assert calls == [], "second arm must postpone the first timer"
    assert _wait(lambda: len(calls) == 1)


def test_cancel_prevents_fire():
    calls = []
    u = IdleUnloader(0.05, lambda: calls.append(1), lambda: False)
    u.arm()
    u.cancel()
    time.sleep(0.15)
    assert calls == []


def test_busy_defers_unload():
    calls = []
    busy = threading.Event()
    busy.set()
    u = IdleUnloader(0.05, lambda: calls.append(1), busy.is_set)
    u.arm()
    time.sleep(0.12)
    assert calls == [], "must not unload under a live decode"
    busy.clear()
    assert _wait(lambda: len(calls) == 1), "re-armed timer fires once idle"


def test_disabled_when_zero():
    calls = []
    u = IdleUnloader(0, lambda: calls.append(1), lambda: False)
    assert not u.enabled
    u.arm()
    time.sleep(0.05)
    assert calls == []
