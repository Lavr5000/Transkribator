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

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


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

    # Check for Whisper
    whisper_ok = False
    try:
        from faster_whisper import WhisperModel
        whisper_ok = True
    except ImportError:
        try:
            import whisper
            whisper_ok = True
        except ImportError:
            pass

    if not whisper_ok:
        missing.append("faster-whisper or openai-whisper")

    if missing:
        print("Missing dependencies:")
        for dep in missing:
            print(f"  - {dep}")
        print("\nInstall with:")
        print("  pip install -r requirements.txt")
        print("\nOr for GPU acceleration:")
        print("  pip install -r requirements-gpu.txt")
        return False

    return True


def main():
    """Main entry point."""
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)

    # Import and run
    from src.main_window import run
    run()


if __name__ == "__main__":
    main()
