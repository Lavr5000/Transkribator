"""Diagnostic test for audio recording."""
import time
import numpy as np
import sys
from io import StringIO
from src.audio_recorder import AudioRecorder

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

def test_recording():
    """Test that audio recording works correctly."""
    print("=" * 60)
    print("AUDIO RECORDING DIAGNOSTIC TEST")
    print("=" * 60)

    # Test 1: Check audio libraries
    print("\n[1] Checking audio libraries...")
    try:
        import sounddevice as sd
        import soundfile as sf
        print("    ✓ sounddevice available")
        print("    ✓ soundfile available")
    except ImportError as e:
        print(f"    ✗ ERROR: {e}")
        return False

    # Test 2: List devices
    print("\n[2] Listing audio devices...")
    devices = AudioRecorder.list_devices()
    if not devices:
        print("    ✗ ERROR: No input devices found!")
        return False
    print(f"    ✓ Found {len(devices)} input device(s):")
    for i, dev in enumerate(devices[:3], 1):
        print(f"      {i}. {dev['name']}")

    # Test 3: Record 2 seconds
    print("\n[3] Recording 2 seconds of audio...")
    recorder = AudioRecorder(sample_rate=16000, channels=1)

    if not recorder.start():
        print("    ✗ ERROR: Failed to start recording!")
        return False
    print("    ✓ Recording started")

    # Monitor audio level
    level_count = 0
    for i in range(20):  # 2 seconds with 100ms intervals
        time.sleep(0.1)
        if recorder.is_recording:
            level_count += 1

    print(f"    ✓ Recording active for {level_count} ticks")

    audio = recorder.stop()
    print("    ✓ Recording stopped")

    # Test 4: Verify audio data
    print("\n[4] Verifying audio data...")
    if audio is None:
        print("    ✗ ERROR: audio is None!")
        return False

    audio_len = len(audio)
    print(f"    Audio length: {audio_len} samples")

    if audio_len == 0:
        print("    ✗ ERROR: Audio is empty (0 samples)!")
        return False

    duration = recorder.get_duration(audio)
    print(f"    Duration: {duration:.2f} seconds")

    if duration < 1.5:
        print(f"    ✗ ERROR: Duration too short! Expected ~2.0s, got {duration:.2f}s")
        return False

    print(f"    ✓ Duration OK ({duration:.2f}s)")

    # Test 5: Check audio levels
    print("\n[5] Checking audio levels...")
    max_level = float(np.abs(audio).max())
    mean_level = float(np.abs(audio).mean())
    print(f"    Max level: {max_level:.6f}")
    print(f"    Mean level: {mean_level:.6f}")

    if max_level < 0.0001:
        print("    ⚠ WARNING: Audio levels very low (microphone issue?)")
        print("    This might cause poor transcription, but recording works.")
    else:
        print(f"    ✓ Audio levels OK")

    # Test 6: Save test file
    print("\n[6] Saving test audio file...")
    try:
        test_file = recorder.save_to_file(audio)
        print(f"    ✓ Saved to: {test_file}")
        import os
        size_kb = os.path.getsize(test_file) / 1024
        print(f"    File size: {size_kb:.1f} KB")
        if size_kb < 10:
            print(f"    ⚠ WARNING: File size seems small for 2 seconds of audio")
    except Exception as e:
        print(f"    ✗ ERROR: Failed to save file: {e}")
        return False

    # Final result
    print("\n" + "=" * 60)
    print("RESULT: ✓ ALL TESTS PASSED")
    print("=" * 60)
    print("\nRecording is working correctly!")
    print("If you're still experiencing issues, the problem is in:")
    print("  - Transcription backend")
    print("  - UI event handling")
    print("  - Configuration/settings")
    return True

if __name__ == "__main__":
    try:
        success = test_recording()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
