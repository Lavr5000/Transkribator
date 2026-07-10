#!/usr/bin/env python3
"""
WhisperTyping - Local Voice Transcription App

A free, unlimited, local voice-to-text application powered by OpenAI's Whisper.
Works offline, no API keys required, runs entirely on your computer.

Usage:
    python main.py

Or after installation:
    whisper-typing
"""

import sys
import os

# Inject HuggingFace token so snapshot_download() can fetch VAD / punctuation
# models. Anonymous access started returning 401 on 2026-04-05. Users should
# set HF_TOKEN (or HUGGING_FACE_HUB_TOKEN) in their environment, or run
# `huggingface-cli login` once. Developers may point TRANSKRIBATOR_KEYSTORE
# at a directory with a .env file (see src/dev_keys.py).
if not os.environ.get("HF_TOKEN") and not os.environ.get("HUGGING_FACE_HUB_TOKEN"):
    try:
        from src.dev_keys import load_env_var
        _hf = load_env_var("HF_TOKEN") or load_env_var("HUGGINGFACE_API_KEY")
        if _hf:
            os.environ["HF_TOKEN"] = _hf
            os.environ["HUGGING_FACE_HUB_TOKEN"] = _hf
    except Exception as _e:
        print(f"[main] HF token lookup failed: {_e}", file=sys.stderr)

# Install CrashReporter early — before any native library imports
from src.crash_reporter import CrashReporter
crash_reporter = CrashReporter()
crash_reporter.install()

# Retry unsent Telegram notifications from previous crashes.
# Runs in a daemon thread so a slow/unreachable Telegram never delays startup.
def _retry_unsent_notifications():
    try:
        from src.notifier import TelegramNotifier
        TelegramNotifier(crash_dir=crash_reporter.crash_dir).send_unsent()
    except Exception:
        pass

import threading
threading.Thread(target=_retry_unsent_notifications, daemon=True).start()


def check_dependencies():
    """Check if all required dependencies are installed."""
    missing = []

    try:
        import PyQt6
    except ImportError:
        missing.append("PyQt6")

    try:
        import sounddevice
    except ImportError:
        missing.append("sounddevice")

    try:
        import soundfile
    except ImportError:
        missing.append("soundfile")

    try:
        import numpy
    except ImportError:
        missing.append("numpy")

    # Check for at least one transcription backend
    has_backend = False

    try:
        import sherpa_onnx
        has_backend = True
    except ImportError:
        pass

    if not has_backend:
        try:
            from faster_whisper import WhisperModel
            has_backend = True
        except ImportError:
            try:
                import whisper
                has_backend = True
            except ImportError:
                pass

    if not has_backend:
        missing.append("sherpa-onnx (recommended) or faster-whisper")

    if missing:
        print("Missing dependencies:")
        for dep in missing:
            print(f"  - {dep}")
        print("\nInstall with:")
        print("  pip install .")
        print("\nOptional extras:")
        print('  pip install ".[nlp]"      # morphology corrections')
        print('  pip install ".[whisper]"  # Whisper backend')
        print('  pip install ".[gpu]"      # CUDA acceleration')
        return False

    return True


def _is_already_running() -> bool:
    """Check if another instance is already running using a lock file."""
    import tempfile, atexit
    lock_path = os.path.join(tempfile.gettempdir(), "transkribator.lock")
    try:
        # Try to read PID from existing lock
        if os.path.exists(lock_path):
            with open(lock_path) as f:
                old_pid = int(f.read().strip())
            # Check if that process is still alive
            import signal
            try:
                os.kill(old_pid, 0)  # signal 0 = check existence
                return True  # Process alive — another instance running
            except OSError:
                pass  # Process dead — stale lock, we can take over

        # Write our PID
        with open(lock_path, "w") as f:
            f.write(str(os.getpid()))
        atexit.register(lambda: os.path.exists(lock_path) and os.unlink(lock_path))
        return False
    except Exception:
        return False  # On error, allow launch


def main():
    """Main entry point."""
    # When launched via watchdog, skip single-instance check
    # (watchdog ensures only one instance runs)
    if "--watchdog" not in sys.argv:
        if _is_already_running():
            print("Transkribator is already running.")
            sys.exit(0)

    # Check dependencies
    if not check_dependencies():
        sys.exit(1)

    # Import and run
    from src.main_window import run
    try:
        exit_code = run() or 0
        sys.exit(exit_code)
    except SystemExit:
        raise  # don't intercept sys.exit()
    except Exception:
        # excepthook already wrote the crash report
        sys.exit(1)


if __name__ == "__main__":
    main()
