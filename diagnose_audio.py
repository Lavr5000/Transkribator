#!/usr/bin/env python3
"""Diagnostic script to test audio recording functionality."""
import sys
import time
import numpy as np

# Add src to path
sys.path.insert(0, str(__file__).rsplit('\\', 1)[0] + '\\src')

from audio_recorder import AudioRecorder

def test_audio_recording():
    """Test audio recording for 2 seconds."""
    print("=" * 60)
    print("AUDIO RECORDING DIAGNOSTIC TEST")
    print("=" * 60)

    # Check audio availability
    print("\n1. Checking audio libraries...")
    if not AudioRecorder.list_devices():
        print("   [ERROR] No audio input devices found!")
        return False
    print(f"   [OK] Found {len(AudioRecorder.list_devices())} audio devices")

    # Create recorder
    print("\n2. Creating AudioRecorder...")
    recorder = AudioRecorder(sample_rate=16000, channels=1)
    print("   [OK] AudioRecorder created")

    # Test recording
    print("\n3. Starting 2-second recording...")
    print("   Speak NOW!")

    start_time = time.time()
    success = recorder.start()
    print(f"   Start result: {success}")

    if not success:
        print("   [ERROR] Failed to start recording!")
        return False

    # Monitor audio level
    levels = []
    for i in range(20):  # 2 seconds with 0.1s intervals
        time.sleep(0.1)
        if recorder.is_recording:
            print(f"   [{(time.time() - start_time):.1f}s] Recording... callback count: {recorder._callback_count if hasattr(recorder, '_callback_count') else 'N/A'}")
        else:
            print(f"   [{(time.time() - start_time):.1f}s] ⚠️ Recording stopped prematurely!")
            break

    print(f"\n4. Stopping recording...")
    audio = recorder.stop()

    if audio is None:
        print("   [ERROR] No audio data collected!")
        print(f"   Recording duration: {time.time() - start_time:.2f}s")
        return False

    duration = recorder.get_duration(audio)
    print(f"   [OK] Audio captured: {len(audio)} samples, {duration:.2f}s")

    # Analyze audio
    print("\n5. Audio analysis:")
    print(f"   Shape: {audio.shape}")
    print(f"   Data type: {audio.dtype}")
    print(f"   Min/Max: {audio.min():.4f} / {audio.max():.4f}")
    print(f"   RMS: {np.sqrt(np.mean(audio**2)):.6f}")
    print(f"   Mean: {np.mean(np.abs(audio)):.6f}")

    # Check if audio has valid data
    rms = np.sqrt(np.mean(audio**2))
    if rms < 0.001:
        print("   [WARNING] Audio signal is very quiet (possible silence)")
    elif rms > 0.1:
        print("   [OK] Audio signal has good level")
    else:
        print("   [OK] Audio signal detected")

    print("\n" + "=" * 60)
    print("TEST COMPLETED SUCCESSFULLY")
    print("=" * 60)
    return True

if __name__ == "__main__":
    try:
        test_audio_recording()
    except Exception as e:
        print(f"\n[EXCEPTION] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
