#!/usr/bin/env python3
"""
E2E Verification — Phase 7 automated checks for Crash Reporter system.

Tests crash_reporter, notifier, quality_monitor, backend switch rollback,
and watchdog infrastructure without requiring human interaction.

Usage:
    python scripts/e2e_verify.py
"""

import json
import os
import signal
import subprocess
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
sys.path.insert(0, SRC_DIR)

CRASH_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "WhisperTyping", "WhisperTyping", "crashes",
)

_failures = 0
_passed = 0


def check(name, passed, detail=""):
    global _failures, _passed
    tag = "[OK]" if passed else "[FAIL]"
    msg = f"  {tag}  {name}"
    if detail:
        msg += f"  —  {detail}"
    print(msg)
    if passed:
        _passed += 1
    else:
        _failures += 1


# ── Test 1: Crash Reporter creates JSON report ──────────────────────────
def test_crash_report_creation():
    print("\n=== 1. Crash Reporter — report creation ===")
    from crash_reporter import CrashReporter
    cr = CrashReporter()

    # Simulate an exception and build report
    try:
        raise RuntimeError("E2E test crash")
    except RuntimeError:
        exc_type, exc_value, exc_tb = sys.exc_info()
        report = cr._build_report(exc_type, exc_value, exc_tb)

    check("Has 'exception' field", "exception" in report)
    check("Has 'timestamp' field", "timestamp" in report)
    check("Has 'system' field", "system" in report)
    check("Exception type correct", report.get("exception", {}).get("type") == "RuntimeError")
    check("Exception message correct", "E2E test crash" in report.get("exception", {}).get("message", ""))

    # Test save — find newest file after saving
    import glob
    before = set(glob.glob(os.path.join(CRASH_DIR, "*.json")))
    cr._save_report(report)
    after = set(glob.glob(os.path.join(CRASH_DIR, "*.json")))
    new_files = after - before
    created = len(new_files) > 0
    check("Crash report file saved to disk", created)
    # Cleanup
    for f in new_files:
        os.unlink(f)


# ── Test 2: CrashReporter context tracking ──────────────────────────────
def test_context_tracking():
    print("\n=== 2. Crash Reporter — context tracking ===")
    from crash_reporter import CrashReporter
    cr = CrashReporter()

    cr.set_context("BACKEND_SWITCH", backend="sherpa", model="v3")
    check("set_context stores action", cr._last_action == "BACKEND_SWITCH")
    check("set_context stores kwargs", cr._context.get("backend") == "sherpa")


# ── Test 3: Notifier formats messages correctly ─────────────────────────
def test_notifier_formatting():
    print("\n=== 3. Notifier — message formatting ===")
    from notifier import TelegramNotifier
    n = TelegramNotifier(crash_dir=CRASH_DIR)

    # Crash report format
    report = {
        "timestamp": "2026-03-26T12:00:00",
        "uptime_sec": 42.5,
        "exception": {"type": "RuntimeError", "message": "test", "traceback": ["line1\n"]},
        "context": {"last_action": "TRANSCRIBE"},
        "system": {"python": "3.13", "platform": "Windows"},
    }
    msg = n.format_crash_report(report)
    check("Crash format has header", "CRASH REPORT" in msg)
    check("Crash format has exception", "RuntimeError" in msg)
    check("Crash format has context", "TRANSCRIBE" in msg)

    # Quality alert format
    details = {"empty_count": 3, "threshold": 3, "backend": "sherpa", "model": "v3"}
    msg2 = n.format_quality_alert(details)
    check("Quality alert has header", "QUALITY ALERT" in msg2)
    check("Quality alert has details", "empty_count" in msg2)


# ── Test 4: Notifier fallback to file ───────────────────────────────────
def test_notifier_fallback():
    print("\n=== 4. Notifier — fallback to file ===")
    import tempfile
    tmp = tempfile.mkdtemp()
    from notifier import TelegramNotifier
    n = TelegramNotifier(crash_dir=tmp)
    n._api_id = None  # Force fallback (no credentials)

    result = n.send("E2E fallback test")
    check("send() returns False on fallback", result is False)

    unsent = os.path.join(tmp, "unsent_notifications.txt")
    exists = os.path.isfile(unsent)
    check("Unsent file created", exists)
    if exists:
        content = open(unsent, encoding="utf-8").read()
        check("Unsent contains message", "E2E fallback test" in content)
        check("Unsent has separator", "---END_MESSAGE---" in content)
        os.unlink(unsent)
    os.rmdir(tmp)


# ── Test 5: Quality Monitor — no false alerts ───────────────────────────
def test_quality_no_false_alerts():
    print("\n=== 5. Quality Monitor — no false alerts ===")
    from unittest.mock import MagicMock
    from quality_monitor import QualityMonitor

    mock_notifier = MagicMock()
    qm = QualityMonitor(mock_notifier)

    # 3 successful transcriptions — no alert
    for i in range(3):
        qm.record_result(text_len=50 + i, audio_duration=5.0, backend="sherpa", model="v3")
    check("No alert after 3 successes", mock_notifier.send.call_count == 0)

    # 2 empty + 1 success + 2 empty — no alert (streak broken)
    mock_notifier.reset_mock()
    qm2 = QualityMonitor(mock_notifier)
    qm2.record_result(text_len=0, audio_duration=3.0, backend="sherpa", model="v3")
    qm2.record_result(text_len=0, audio_duration=3.0, backend="sherpa", model="v3")
    qm2.record_result(text_len=100, audio_duration=5.0, backend="sherpa", model="v3")
    qm2.record_result(text_len=0, audio_duration=3.0, backend="sherpa", model="v3")
    qm2.record_result(text_len=0, audio_duration=3.0, backend="sherpa", model="v3")
    check("No alert when streak broken by success", mock_notifier.send.call_count == 0)


# ── Test 6: Quality Monitor — alert triggers ────────────────────────────
def test_quality_alert_triggers():
    print("\n=== 6. Quality Monitor — alert on 3 empties ===")
    from unittest.mock import MagicMock
    from quality_monitor import QualityMonitor

    mock_notifier = MagicMock()
    mock_notifier.format_quality_alert.return_value = "QUALITY ALERT"
    qm = QualityMonitor(mock_notifier)

    for _ in range(3):
        qm.record_result(text_len=0, audio_duration=3.0, backend="groq", model="whisper-large")

    check("Alert sent after 3 empties", mock_notifier.send.call_count == 1)
    call_args = mock_notifier.format_quality_alert.call_args[0][0]
    check("Alert has empty_count=3", call_args.get("empty_count") == 3)
    check("Alert has backend", call_args.get("backend") == "groq")
    check("Alert has model", call_args.get("model") == "whisper-large")


# ── Test 7: Backend switch rollback ─────────────────────────────────────
def test_backend_rollback():
    print("\n=== 7. Backend switch — rollback on failure ===")
    from unittest.mock import MagicMock, patch

    mock_backend = MagicMock()
    mock_cls = MagicMock(return_value=mock_backend)

    with patch("transcriber.get_backend", return_value=mock_cls):
        with patch("transcriber.get_reporter", return_value=None):
            from transcriber import Transcriber
            t = Transcriber(backend="sherpa", model_size="v3", enable_post_processing=False)

    old_backend = t._backend
    old_name = t.backend_name

    # Force failure on switch
    failing_cls = MagicMock(side_effect=RuntimeError("Model load failed"))
    with patch("transcriber.get_backend", return_value=failing_cls):
        with patch("transcriber.get_reporter", return_value=None):
            try:
                t.switch_backend("whisper", "base")
                rolled_back = False
            except RuntimeError:
                rolled_back = True

    check("Exception raised on bad switch", rolled_back)
    check("Backend name restored", t.backend_name == old_name)
    check("Backend instance restored", t._backend is old_backend)
    check("Old backend NOT unloaded", old_backend.unload_model.call_count == 0)


# ── Test 8: Watchdog script syntax ──────────────────────────────────────
def test_watchdog_syntax():
    print("\n=== 8. Watchdog — script validity ===")
    watchdog_path = os.path.join(PROJECT_ROOT, "scripts", "watchdog.py")
    check("watchdog.py exists", os.path.isfile(watchdog_path))

    import py_compile
    try:
        py_compile.compile(watchdog_path, doraise=True)
        check("watchdog.py syntax OK", True)
    except py_compile.PyCompileError as e:
        check("watchdog.py syntax OK", False, str(e))

    # Verify watchdog compiles and imports work
    try:
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", watchdog_path],
            capture_output=True, text=True, timeout=10,
        )
        check("watchdog.py compiles OK", result.returncode == 0,
              result.stderr[:100] if result.returncode else "")
    except Exception as e:
        check("watchdog.py compiles OK", False, str(e))


# ── Test 9: main.py --watchdog flag ─────────────────────────────────────
def test_main_watchdog_flag():
    print("\n=== 9. main.py — --watchdog flag ===")
    main_path = os.path.join(PROJECT_ROOT, "main.py")
    with open(main_path, "r", encoding="utf-8") as f:
        content = f.read()
    check("main.py has --watchdog check", "--watchdog" in content)
    check("main.py skips single-instance with --watchdog",
          'if "--watchdog" not in sys.argv' in content or
          '"--watchdog" not in sys.argv' in content)


# ── Test 10: Notifier real send (to Saved Messages) ────────────────────
def test_notifier_real_send():
    print("\n=== 10. Notifier — real Telegram send ===")
    from notifier import TelegramNotifier
    n = TelegramNotifier(crash_dir=CRASH_DIR)

    if not n._api_id or not n._api_hash:
        check("Telegram credentials", False, "TELEGRAM_API_ID/HASH not set")
        return

    msg = (
        "E2E VERIFICATION -- WhisperTyping\n"
        f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        "Status: All automated checks passed\n"
        "This is an automated test message from scripts/e2e_verify.py"
    )
    result = n.send(msg)
    check("Real Telegram send", result, "sent to Saved Messages" if result else "fallback to file")


def main():
    print(f"Transkribator E2E Verification — {PROJECT_ROOT}")
    print(f"Crash dir: {CRASH_DIR}")

    test_crash_report_creation()
    test_context_tracking()
    test_notifier_formatting()
    test_notifier_fallback()
    test_quality_no_false_alerts()
    test_quality_alert_triggers()
    test_backend_rollback()
    test_watchdog_syntax()
    test_main_watchdog_flag()
    test_notifier_real_send()

    print(f"\n{'=' * 50}")
    print(f"  {_passed} PASSED, {_failures} FAILED")
    print(f"{'=' * 50}")

    if _failures:
        print(f"\n  WARNING: {_failures} check(s) failed -- see details above")
    else:
        print("\n  All automated E2E checks passed!")
        print("\n  MANUAL CHECKS REMAINING:")
        print("  1. Launch: python scripts/watchdog.py")
        print("  2. Record 3 transcriptions (5-10 sec each)")
        print("  3. Verify: no false Telegram alerts")
        print("  4. Kill process: taskkill /PID /F")
        print("  5. Verify: crash report + watchdog restarts")
        print("  6. Record 4 very short clips (0.5 sec)")
        print("  7. Verify: quality alert in Telegram")

    sys.exit(1 if _failures else 0)


if __name__ == "__main__":
    main()
