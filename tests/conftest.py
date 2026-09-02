"""Shared test isolation.

The event log writes to the real user config dir (%LOCALAPPDATA%\\WhisperTyping),
which is also where the live app writes. Without this fixture, a test that
calls recorder.open_stream()/stop() against a stubbed sounddevice appends
`capture_open` / `capture_fallback` / `capture_degraded` rows to the OWNER'S
live log — and the burn-in aggregator then counts them as real capture
problems. Happened on 2026-07-30: ~30 synthetic rows landed in the live log.

Autouse, so every test in the suite is isolated by default.
"""

import logging

import pytest

from src import event_log


@pytest.fixture(autouse=True)
def isolate_event_log(tmp_path, monkeypatch):
    """Point the event log at a per-test temp file."""
    target = tmp_path / "events.jsonl"
    monkeypatch.setattr(event_log, "_get_event_log_path", lambda: target)
    return target


@pytest.fixture(autouse=True)
def isolate_app_log():
    """Detach the app's debug.log file handler for the duration of a test.

    Importing `main_window` attaches a RotatingFileHandler to the shared
    "transkribator" logger, so test runs used to interleave synthetic lines
    (e.g. RESEARCH_MODE_BLOCKED, absurd transcription times) into the live
    diagnostic log the owner and future sessions read.
    """
    logger = logging.getLogger("transkribator")
    detached = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
    for h in detached:
        logger.removeHandler(h)
    try:
        yield
    finally:
        for h in detached:
            logger.addHandler(h)
