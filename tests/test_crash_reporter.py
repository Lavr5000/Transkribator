"""Tests for CrashReporter (Phase 2)."""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from crash_reporter import CrashReporter


@pytest.fixture
def crash_dir(tmp_path):
    """Temporary crash directory."""
    d = tmp_path / "crashes"
    d.mkdir()
    return d


@pytest.fixture
def reporter(crash_dir):
    """CrashReporter with temp crash dir, not installed globally."""
    return CrashReporter(crash_dir=str(crash_dir))


class TestCrashReporter:
    def test_build_report_fields(self, reporter):
        """All required fields are present in crash report."""
        try:
            raise ValueError("test error")
        except ValueError:
            exc_type, exc_value, exc_tb = sys.exc_info()
            report = reporter._build_report(exc_type, exc_value, exc_tb)

        assert report["version"] == 1
        assert "timestamp" in report
        assert "uptime_sec" in report
        assert report["exit_type"] == "exception"
        assert report["exception"]["type"] == "ValueError"
        assert report["exception"]["message"] == "test error"
        assert len(report["exception"]["traceback"]) > 0
        assert "last_action" in report["context"]
        assert "python" in report["system"]
        assert "platform" in report["system"]
        assert isinstance(report["log_tail"], list)

    def test_save_report_creates_file(self, reporter, crash_dir):
        """Crash report JSON file is created in crash_dir."""
        try:
            raise RuntimeError("file creation test")
        except RuntimeError:
            exc_type, exc_value, exc_tb = sys.exc_info()
            report = reporter._build_report(exc_type, exc_value, exc_tb)
            reporter._save_report(report)

        files = list(crash_dir.glob("*.json"))
        assert len(files) == 1
        data = json.loads(files[0].read_text(encoding="utf-8"))
        assert data["exception"]["type"] == "RuntimeError"
        assert data["exception"]["message"] == "file creation test"

    def test_excepthook_catches_exception(self, reporter, crash_dir):
        """on_exception writes crash report when called as excepthook."""
        try:
            raise TypeError("hook test")
        except TypeError:
            exc_type, exc_value, exc_tb = sys.exc_info()
            reporter.on_exception(exc_type, exc_value, exc_tb)

        files = list(crash_dir.glob("*.json"))
        assert len(files) == 1
        data = json.loads(files[0].read_text(encoding="utf-8"))
        assert data["exception"]["type"] == "TypeError"

    def test_context_tracking(self, reporter, crash_dir):
        """set_context updates last_action and backend info in report."""
        reporter.set_context("MODEL_SWITCH", backend="sherpa", model="giga-am-v3-ru")

        try:
            raise RuntimeError("context test")
        except RuntimeError:
            exc_type, exc_value, exc_tb = sys.exc_info()
            report = reporter._build_report(exc_type, exc_value, exc_tb)

        assert report["context"]["last_action"] == "MODEL_SWITCH"
        assert report["context"]["backend"] == "sherpa"
        assert report["context"]["model"] == "giga-am-v3-ru"

    def test_log_tail_reading(self, reporter, crash_dir):
        """_read_log_tail returns last N lines from log file."""
        log_file = crash_dir.parent / "debug.log"
        lines = [f"[2026-03-26] line {i}" for i in range(30)]
        log_file.write_text("\n".join(lines), encoding="utf-8")

        tail = reporter._read_log_tail(10, log_path=str(log_file))
        assert len(tail) == 10
        assert tail[-1] == "[2026-03-26] line 29"
        assert tail[0] == "[2026-03-26] line 20"
