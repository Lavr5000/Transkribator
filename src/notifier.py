"""
Telegram Notifier — sends crash reports to Saved Messages via Telethon.

Usage:
    from notifier import TelegramNotifier
    notifier = TelegramNotifier()
    notifier.send(notifier.format_crash_report(report_dict))
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path

_ENV_PATH = Path.home() / ".claude" / "0 ProEKTi" / "blogger" / ".env"
_SESSION_PATH = str(
    Path.home() / ".claude" / "0 ProEKTi" / "blogger" / "sessions" / "telegram_session"
)

_MAX_MESSAGE_LEN = 4000  # Telegram limit is 4096, leave margin


class TelegramNotifier:
    def __init__(self, crash_dir=None):
        if crash_dir is None:
            crash_dir = os.path.join(
                os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                "WhisperTyping", "WhisperTyping", "crashes",
            )
        self.crash_dir = crash_dir
        self.unsent_path = os.path.join(crash_dir, "unsent_notifications.txt")

        # Load credentials from .env (best-effort)
        try:
            from dotenv import load_dotenv
            load_dotenv(_ENV_PATH)
        except ImportError:
            pass

        raw_id = os.environ.get("TELEGRAM_API_ID")
        self._api_id = int(raw_id) if raw_id else None
        self._api_hash = os.environ.get("TELEGRAM_API_HASH")
        self._session_path = _SESSION_PATH

    def format_crash_report(self, report):
        """Format crash report dict into a human-readable Telegram message."""
        exc = report.get("exception", {})
        ctx = report.get("context", {})
        sys_info = report.get("system", {})

        tb_lines = exc.get("traceback", [])
        # Keep last 5 traceback lines
        tb_text = "".join(tb_lines[-5:]).rstrip()

        lines = [
            "CRASH REPORT -- WhisperTyping",
            f"Timestamp: {report.get('timestamp', 'N/A')}",
            f"Uptime: {report.get('uptime_sec', '?')}s",
            "",
            f"Exception: {exc.get('type', 'Unknown')}",
            f"Message: {exc.get('message', '')}",
            "",
            "Traceback:",
            tb_text,
            "",
            f"Context: {ctx.get('last_action', 'N/A')}",
            f"System: Python {sys_info.get('python', '?')[:20]}, {sys_info.get('platform', '?')}",
        ]
        msg = "\n".join(lines)
        if len(msg) > _MAX_MESSAGE_LEN:
            msg = msg[:_MAX_MESSAGE_LEN] + "\n... (truncated)"
        return msg

    def format_quality_alert(self, details):
        """Format quality degradation alert into a Telegram message."""
        lines = [
            "QUALITY ALERT -- WhisperTyping",
            f"Time: {datetime.now().isoformat()}",
            "",
        ]
        for key, value in details.items():
            lines.append(f"{key}: {value}")
        return "\n".join(lines)

    def _try_send(self, message):
        """Attempt to send via Telegram. Returns True on success, no fallback."""
        try:
            if not self._api_id or not self._api_hash:
                return False
            asyncio.run(self._send_async(message))
            return True
        except Exception:
            return False

    def send(self, message):
        """Send message to Telegram, fall back to file on failure."""
        if self._try_send(message):
            return True
        try:
            self._fallback_to_file(message)
        except Exception:
            pass
        return False

    async def _send_async(self, message):
        """Connect to Telegram and send message to Saved Messages."""
        from telethon import TelegramClient

        client = TelegramClient(self._session_path, self._api_id, self._api_hash)
        try:
            await client.connect()
            if not await client.is_user_authorized():
                raise ConnectionError("Telegram session not authorized")
            await client.send_message("me", message)
        finally:
            await client.disconnect()

    def _fallback_to_file(self, message):
        """Append message to unsent_notifications.txt."""
        os.makedirs(os.path.dirname(self.unsent_path), exist_ok=True)
        with open(self.unsent_path, "a", encoding="utf-8") as f:
            f.write(message)
            f.write("\n---END_MESSAGE---\n")

    def send_unsent(self):
        """Retry sending queued messages. Returns count of successfully sent."""
        try:
            if not os.path.isfile(self.unsent_path):
                return 0
            with open(self.unsent_path, "r", encoding="utf-8") as f:
                content = f.read()
            if not content.strip():
                os.unlink(self.unsent_path)
                return 0

            messages = [m.strip() for m in content.split("---END_MESSAGE---") if m.strip()]
            failed = []
            sent_count = 0

            for msg in messages:
                if self._try_send(msg):
                    sent_count += 1
                else:
                    failed.append(msg)

            if failed:
                with open(self.unsent_path, "w", encoding="utf-8") as f:
                    for msg in failed:
                        f.write(msg)
                        f.write("\n---END_MESSAGE---\n")
            else:
                os.unlink(self.unsent_path)

            return sent_count
        except Exception:
            return 0
