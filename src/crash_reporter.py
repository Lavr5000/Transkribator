"""
Crash Reporter — catches unhandled exceptions and writes JSON crash reports.

Usage:
    from crash_reporter import CrashReporter
    reporter = CrashReporter()
    reporter.install()  # sets sys.excepthook + faulthandler
    reporter.set_context("MODEL_SWITCH", backend="sherpa", model="giga-am-v3-ru")
"""

import faulthandler
import json
import os
import platform
import sys
import time
import traceback
from datetime import datetime


_instance = None


def get_reporter():
    """Get the global CrashReporter instance (may be None if not installed)."""
    return _instance


class CrashReporter:
    def __init__(self, crash_dir=None, log_path=None):
        if crash_dir is None:
            crash_dir = os.path.join(
                os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                "WhisperTyping", "WhisperTyping", "crashes"
            )
        self.crash_dir = crash_dir
        self.log_path = log_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "debug.log"
        )
        self._start_time = time.monotonic()
        self._last_action = "startup"
        self._context = {}
        self._original_excepthook = sys.excepthook
        self._fault_file = None

    def install(self):
        """Install sys.excepthook and enable faulthandler."""
        global _instance
        _instance = self
        os.makedirs(self.crash_dir, exist_ok=True)

        # faulthandler for C-level crashes (SIGSEGV, SIGABRT)
        try:
            self._fault_file = open(
                os.path.join(self.crash_dir, "faulthandler.log"), "w"
            )
            faulthandler.enable(file=self._fault_file, all_threads=True)
        except Exception:
            faulthandler.enable()

        # Python-level exception hook
        self._original_excepthook = sys.excepthook
        sys.excepthook = self.on_exception

    def set_context(self, action, **kwargs):
        """Update last action and context for crash reports."""
        self._last_action = action
        self._context.update(kwargs)

    def on_exception(self, exc_type, exc_value, exc_tb):
        """sys.excepthook — build and save crash report, then delegate."""
        try:
            report = self._build_report(exc_type, exc_value, exc_tb)
            self._save_report(report)
            self._notify_telegram(report)
        except Exception:
            pass  # crash reporter must never crash
        self._original_excepthook(exc_type, exc_value, exc_tb)

    def _build_report(self, exc_type, exc_value, exc_tb):
        """Build crash report dict."""
        report = {
            "version": 1,
            "timestamp": datetime.now().isoformat(),
            "uptime_sec": round(time.monotonic() - self._start_time, 1),
            "exit_type": "exception",
            "exception": {
                "type": exc_type.__name__ if exc_type else "Unknown",
                "message": str(exc_value) if exc_value else "",
                "traceback": traceback.format_tb(exc_tb) if exc_tb else [],
            },
            "context": {
                "last_action": self._last_action,
                **self._context,
            },
            "system": {
                "python": sys.version,
                "platform": platform.platform(),
            },
            "log_tail": self._read_log_tail(20),
        }

        # Optional RAM info
        try:
            import psutil
            mem = psutil.virtual_memory()
            report["system"]["ram_used_mb"] = mem.used // (1024 * 1024)
            report["system"]["ram_total_mb"] = mem.total // (1024 * 1024)
        except ImportError:
            pass

        return report

    def _save_report(self, report):
        """Write crash report JSON to crash_dir."""
        os.makedirs(self.crash_dir, exist_ok=True)
        filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".json"
        filepath = os.path.join(self.crash_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    def _notify_telegram(self, report):
        """Send crash report to Telegram Saved Messages (best-effort)."""
        try:
            from notifier import TelegramNotifier
            notifier = TelegramNotifier(crash_dir=self.crash_dir)
            message = notifier.format_crash_report(report)
            notifier.send(message)
        except Exception:
            pass  # notification must never crash the app

    def _read_log_tail(self, n=20, log_path=None):
        """Read last n lines from debug.log."""
        path = log_path or self.log_path
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
                return [line.rstrip() for line in lines[-n:]]
        except Exception:
            return []
