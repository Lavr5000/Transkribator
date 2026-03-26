"""Tests for TelegramNotifier (Phase 3)."""

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture
def crash_dir(tmp_path):
    """Temporary crash directory."""
    d = tmp_path / "crashes"
    d.mkdir()
    return d


@pytest.fixture
def notifier(crash_dir):
    """TelegramNotifier with tmp crash dir and dummy credentials."""
    with patch.dict(os.environ, {
        "TELEGRAM_API_ID": "12345",
        "TELEGRAM_API_HASH": "testhash",
    }):
        from notifier import TelegramNotifier
        return TelegramNotifier(crash_dir=str(crash_dir))


class TestTelegramNotifier:
    def test_format_crash_message(self, notifier):
        """format_crash_report returns readable message with key fields."""
        report = {
            "version": 1,
            "timestamp": "2026-03-26T12:00:00",
            "uptime_sec": 42.5,
            "exit_type": "exception",
            "exception": {
                "type": "RuntimeError",
                "message": "test crash",
                "traceback": [
                    '  File "main.py", line 1\n',
                    "    raise RuntimeError\n",
                ],
            },
            "context": {"last_action": "MODEL_SWITCH"},
            "system": {"python": "3.11.0", "platform": "Windows-10"},
            "log_tail": [],
        }
        msg = notifier.format_crash_report(report)
        assert "CRASH REPORT" in msg
        assert "RuntimeError" in msg
        assert "test crash" in msg
        assert "MODEL_SWITCH" in msg
        assert "42.5" in msg

    def test_format_quality_alert(self, notifier):
        """format_quality_alert returns readable message with details."""
        details = {"empty_count": 3, "threshold": 3, "last_audio_sec": 5.2}
        msg = notifier.format_quality_alert(details)
        assert "QUALITY ALERT" in msg
        assert "3" in msg

    def test_fallback_to_file(self, notifier, crash_dir):
        """On Telegram error, message is written to unsent_notifications.txt."""
        with patch.object(notifier, "_try_send", return_value=False):
            notifier.send("Test crash notification")

        unsent_file = crash_dir / "unsent_notifications.txt"
        assert unsent_file.exists()
        content = unsent_file.read_text(encoding="utf-8")
        assert "Test crash notification" in content
        assert "---END_MESSAGE---" in content

    def test_unsent_queue(self, notifier, crash_dir):
        """Unsent messages are retried and file is cleaned up on success."""
        unsent_file = crash_dir / "unsent_notifications.txt"
        unsent_file.write_text(
            "Message 1\n---END_MESSAGE---\nMessage 2\n---END_MESSAGE---\n",
            encoding="utf-8",
        )

        with patch.object(notifier, "_try_send", return_value=True) as mock_send:
            count = notifier.send_unsent()

        assert count == 2
        assert mock_send.call_count == 2
        assert not unsent_file.exists()
