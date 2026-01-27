#!/usr/bin/env python3
"""Test script for Sherpa backend with GigaAM model."""

import sys
import os

# Change to script directory and add to path
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from src.transcriber import Transcriber

print("=" * 60)
print("Testing Sherpa backend with GigaAM model")
print("=" * 60)

try:
    print("\n[1/3] Initializing Transcriber...")
    transcriber = Transcriber(
        backend="sherpa",
        model_size="giga-am-v2-ru",
        device="cpu",
        language="auto",
        enable_post_processing=True
    )
    print("[OK] Transcriber object created")

    # Check if transcriber has the model loaded
    if hasattr(transcriber, 'model'):
        print(f"[OK] Model loaded: {transcriber.model}")
    else:
        print("[ERROR] No model attribute found")

    # Test with dummy audio (1 second of silence)
    import numpy as np
    print("\n[2/3] Creating test audio (1 sec silence)...")
    sample_rate = 16000
    audio = np.zeros(sample_rate, dtype=np.float32)
    print("[OK] Test audio created")

    print("\n[3/3] Testing transcription...")
    text, duration = transcriber.transcribe(audio, sample_rate)
    print(f"[OK] Transcription complete in {duration:.2f}s")
    print(f"  Result: '{text}'")

    print("\n" + "=" * 60)
    print("SUCCESS: Sherpa backend works!")
    print("=" * 60)

except Exception as e:
    print("\n" + "=" * 60)
    print(f"ERROR: {type(e).__name__}")
    print(f"Message: {str(e)}")
    print("=" * 60)
    import traceback
    traceback.print_exc()
    sys.exit(1)
