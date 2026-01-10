"""Test script for Sherpa-ONNX integration."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.backends import SherpaBackend, WhisperBackend
import numpy as np

def test_sherpa_backend():
    """Test Sherpa-ONNX backend."""
    print("=" * 60)
    print("Testing Sherpa-ONNX Backend")
    print("=" * 60)

    try:
        # Create backend instance
        backend = SherpaBackend(
            model_size="giga-am-v2-ru",
            language="ru"
        )

        print(f"\n[INFO] Backend info:")
        info = backend.get_model_info()
        for key, value in info.items():
            print(f"  {key}: {value}")

        # Check if model files exist
        if info.get("model_files_exist"):
            print("\n[SUCCESS] Model files found!")
        else:
            print("\n[ERROR] Model files not found!")
            return False

        # Load model
        print("\n[INFO] Loading model...")
        backend.load_model()
        print("[SUCCESS] Model loaded!")

        # Create test audio (silence with some noise)
        print("\n[INFO] Creating test audio (1 second of silence)...")
        sample_rate = 16000
        duration = 1.0  # seconds
        audio = np.random.randn(int(sample_rate * duration)).astype(np.float32) * 0.001

        # Test transcription
        print("\n[INFO] Testing transcription...")
        text, time_taken = backend.transcribe(audio, sample_rate)
        print(f"[SUCCESS] Transcription completed in {time_taken:.2f}s")
        print(f"[INFO] Result: '{text}'")

        # Unload model
        backend.unload_model()
        print("\n[SUCCESS] Model unloaded")

        return True

    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_whisper_backend():
    """Test Whisper backend for comparison."""
    print("\n" + "=" * 60)
    print("Testing Whisper Backend (for comparison)")
    print("=" * 60)

    try:
        backend = WhisperBackend(
            model_size="base",
            language="ru"
        )

        print(f"\n[INFO] Backend info:")
        info = backend.get_model_info()
        for key, value in info.items():
            print(f"  {key}: {value}")

        return True

    except Exception as e:
        print(f"\n[ERROR] Whisper backend test failed: {e}")
        return False

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Sherpa-ONNX Integration Test")
    print("=" * 60)

    # Test Sherpa backend
    sherpa_ok = test_sherpa_backend()

    # Test Whisper backend
    whisper_ok = test_whisper_backend()

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"Sherpa-ONNX: {'OK' if sherpa_ok else 'FAILED'}")
    print(f"Whisper: {'OK' if whisper_ok else 'FAILED'}")
    print("=" * 60)

    if sherpa_ok:
        print("\n[SUCCESS] Sherpa-ONNX integration is working!")
    else:
        print("\n[ERROR] Sherpa-ONNX integration has issues")
