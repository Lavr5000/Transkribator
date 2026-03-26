"""Tests for QualityMonitor (Phase 4)."""

import os
import sys
import time
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture
def mock_notifier():
    """Mock TelegramNotifier — no real Telegram calls."""
    notifier = MagicMock()
    notifier.format_quality_alert.return_value = "QUALITY ALERT -- WhisperTyping"
    notifier.send.return_value = False
    return notifier


@pytest.fixture
def monitor(mock_notifier):
    """QualityMonitor with mocked notifier."""
    from quality_monitor import QualityMonitor
    return QualityMonitor(mock_notifier)


class TestQualityMonitor:
    def test_single_empty_no_alert(self, monitor, mock_notifier):
        """One empty transcription does NOT trigger alert."""
        monitor.record_result(text_len=0, audio_duration=3.0, backend="sherpa", model="v3")
        mock_notifier.send.assert_not_called()

    def test_three_empty_triggers_alert(self, monitor, mock_notifier):
        """3 consecutive empty transcriptions trigger a quality alert."""
        for _ in range(3):
            monitor.record_result(text_len=0, audio_duration=3.0, backend="sherpa", model="v3")
        mock_notifier.format_quality_alert.assert_called_once()
        mock_notifier.send.assert_called_once()

    def test_success_resets_counter(self, monitor, mock_notifier):
        """Successful transcription resets the empty streak."""
        monitor.record_result(text_len=0, audio_duration=3.0, backend="sherpa", model="v3")
        monitor.record_result(text_len=0, audio_duration=3.0, backend="sherpa", model="v3")
        # Success in the middle resets streak
        monitor.record_result(text_len=50, audio_duration=5.0, backend="sherpa", model="v3")
        monitor.record_result(text_len=0, audio_duration=3.0, backend="sherpa", model="v3")
        monitor.record_result(text_len=0, audio_duration=3.0, backend="sherpa", model="v3")
        # Only 2 consecutive empties after success — no alert
        mock_notifier.send.assert_not_called()

    def test_alert_includes_context(self, monitor, mock_notifier):
        """Alert details contain backend, model, and empty_count."""
        for _ in range(3):
            monitor.record_result(text_len=0, audio_duration=4.0, backend="groq", model="whisper-large")
        # Check the details dict passed to format_quality_alert
        call_args = mock_notifier.format_quality_alert.call_args[0][0]
        assert call_args["empty_count"] == 3
        assert call_args["backend"] == "groq"
        assert call_args["model"] == "whisper-large"
        assert "threshold" in call_args

    def test_window_expiration(self, monitor, mock_notifier):
        """Results older than WINDOW_MINUTES are ignored."""
        expired_time = time.time() - (monitor.WINDOW_MINUTES * 60 + 1)
        # Inject 2 expired empty results directly
        for _ in range(2):
            monitor._results.append({
                "time": expired_time,
                "text_len": 0,
                "audio_duration": 3.0,
                "backend": "sherpa",
                "model": "v3",
            })
        # Add 1 fresh empty — total 3 empties but only 1 is within window
        monitor.record_result(text_len=0, audio_duration=3.0, backend="sherpa", model="v3")
        mock_notifier.send.assert_not_called()
