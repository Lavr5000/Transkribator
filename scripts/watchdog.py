#!/usr/bin/env python3
"""
Watchdog — external process monitor for Transkribator.

Launches main.py as a subprocess, monitors exit codes, and restarts on crash.
Sends Telegram notifications on each restart and stops after too many crashes.

Usage:
    python scripts/watchdog.py
"""

import os
import sys
import subprocess
import time
import json
import logging

# Project root = parent of scripts/
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
sys.path.insert(0, SRC_DIR)

# Watchdog configuration
MAX_RESTARTS = 3          # Max restarts within the time window
WINDOW_SECONDS = 5 * 60  # 5-minute sliding window
RESTART_DELAY = 2         # Seconds to wait before restarting

# Crash directory
CRASH_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "WhisperTyping", "WhisperTyping", "crashes",
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [watchdog] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("watchdog")


def _get_latest_crash_report():
    """Read the most recent crash report from crashes/ directory."""
    try:
        if not os.path.isdir(CRASH_DIR):
            return None
        reports = sorted(
            [f for f in os.listdir(CRASH_DIR) if f.startswith("crash_") and f.endswith(".json")],
            reverse=True,
        )
        if not reports:
            return None
        path = os.path.join(CRASH_DIR, reports[0])
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _send_notification(message):
    """Send Telegram notification via TelegramNotifier."""
    try:
        from notifier import TelegramNotifier
        notifier = TelegramNotifier(crash_dir=CRASH_DIR)
        notifier.send(message)
        logger.info("Telegram notification sent")
    except Exception as e:
        logger.warning("Failed to send Telegram notification: %s", e)


def _format_restart_message(exit_code, restart_count, crash_report=None):
    """Format restart notification message."""
    lines = [
        "WATCHDOG RESTART -- WhisperTyping",
        f"Exit code: {exit_code}",
        f"Restart #{restart_count}/{MAX_RESTARTS}",
        f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}",
    ]
    if crash_report:
        exc = crash_report.get("exception", {})
        if exc:
            lines.append(f"Exception: {exc.get('type', '?')}: {exc.get('message', '?')}")
        ctx = crash_report.get("context", {})
        if ctx.get("last_action"):
            lines.append(f"Context: {ctx['last_action']}")
    return "\n".join(lines)


def _format_limit_message(restart_count):
    """Format message when restart limit is exceeded."""
    return (
        "WATCHDOG STOPPED -- WhisperTyping\n"
        f"Too many crashes: {restart_count} restarts in {WINDOW_SECONDS // 60} minutes\n"
        f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        "Manual restart required."
    )


def run_watchdog():
    """Main watchdog loop — launch, monitor, restart."""
    restart_times = []  # Timestamps of recent restarts
    main_py = os.path.join(PROJECT_ROOT, "main.py")

    if not os.path.isfile(main_py):
        logger.error("main.py not found: %s", main_py)
        sys.exit(1)

    logger.info("Watchdog started, monitoring: %s", main_py)

    while True:
        # Launch main.py
        logger.info("Launching main.py (PID will follow)...")
        proc = subprocess.Popen(
            [sys.executable, main_py, "--watchdog"],
            cwd=PROJECT_ROOT,
        )
        logger.info("main.py started with PID %d", proc.pid)

        # Wait for process to exit
        exit_code = proc.wait()
        logger.info("main.py exited with code %d", exit_code)

        # Normal exit — stop watchdog
        if exit_code == 0:
            logger.info("Clean exit (code 0), watchdog stopping")
            break

        # Crash — check restart budget
        now = time.time()
        restart_times = [t for t in restart_times if now - t < WINDOW_SECONDS]

        if len(restart_times) >= MAX_RESTARTS:
            logger.error(
                "Restart limit reached (%d in %d min), stopping",
                MAX_RESTARTS, WINDOW_SECONDS // 60,
            )
            _send_notification(_format_limit_message(len(restart_times)))
            sys.exit(1)

        # Register this restart
        restart_times.append(now)
        restart_count = len(restart_times)

        # Read crash report if available
        crash_report = _get_latest_crash_report()

        # Send notification
        msg = _format_restart_message(exit_code, restart_count, crash_report)
        logger.info("Sending restart notification...")
        _send_notification(msg)

        # Wait before restart
        logger.info("Restarting in %d seconds...", RESTART_DELAY)
        time.sleep(RESTART_DELAY)


if __name__ == "__main__":
    run_watchdog()
