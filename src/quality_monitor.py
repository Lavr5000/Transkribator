"""
Quality Monitor — tracks transcription quality degradation.

Sends Telegram alert when consecutive empty transcriptions exceed threshold.

Usage:
    from quality_monitor import QualityMonitor
    from notifier import TelegramNotifier
    monitor = QualityMonitor(TelegramNotifier())
    monitor.record_result(text_len=0, audio_duration=3.0, backend="sherpa", model="v3")
"""

import logging
import time

logger = logging.getLogger(__name__)


class QualityMonitor:
    ALERT_THRESHOLD = 3   # Alert after N consecutive empties
    WINDOW_MINUTES = 10   # Observation window

    def __init__(self, notifier):
        self._notifier = notifier
        self._results = []

    def record_result(self, text_len, audio_duration=0, backend="", model=""):
        """Record a transcription result and check for quality degradation."""
        self._results.append({
            "time": time.time(),
            "text_len": text_len,
            "audio_duration": audio_duration,
            "backend": backend,
            "model": model,
        })
        self._prune_expired()
        self._check_quality()

    def _prune_expired(self):
        """Remove results older than WINDOW_MINUTES."""
        cutoff = time.time() - self.WINDOW_MINUTES * 60
        self._results = [r for r in self._results if r["time"] >= cutoff]

    def _check_quality(self):
        """Check if last ALERT_THRESHOLD results are all empty."""
        if len(self._results) < self.ALERT_THRESHOLD:
            return
        recent = self._results[-self.ALERT_THRESHOLD:]
        if all(r["text_len"] == 0 for r in recent):
            self._send_alert(recent)

    def _send_alert(self, recent):
        """Send quality alert via notifier."""
        last = recent[-1]
        details = {
            "empty_count": len(recent),
            "threshold": self.ALERT_THRESHOLD,
            "backend": last["backend"],
            "model": last["model"],
            "last_audio_sec": last["audio_duration"],
            "window_minutes": self.WINDOW_MINUTES,
        }
        msg = self._notifier.format_quality_alert(details)
        self._notifier.send(msg)
        logger.warning("Quality alert sent: %d consecutive empty transcriptions", len(recent))
        # Clear results to avoid repeated alerts
        self._results.clear()
