#!/usr/bin/env python3
"""Profile transcription performance to find bottlenecks."""
import time
import numpy as np
import os

def profile_step(name):
    """Context manager for profiling."""
    class Timer:
        def __init__(self, name):
            self.name = name
        def __enter__(self):
            self.start = time.time()
            return self
        def __exit__(self, *args):
            elapsed = time.time() - self.start
            print(f"  [{self.name}]: {elapsed:.3f}s")
            return False
    return Timer(name)


def main():
    print("=" * 60)
    print("TRANSCRIPTION PROFILER")
    print("=" * 60)

    # Generate test audio (5 seconds of speech-like noise)
    sample_rate = 16000
    duration = 5  # seconds
    audio = np.random.randn(sample_rate * duration).astype(np.float32) * 0.1

    print(f"\nTest audio: {duration}s @ {sample_rate}Hz")
    print(f"CPU cores: {os.cpu_count()}")
    print()

    # ============================================
    # Test 1: Sherpa Backend Only
    # ============================================
    print("=" * 60)
    print("TEST 1: SherpaBackend (без post-processing)")
    print("=" * 60)

    with profile_step("Import SherpaBackend"):
        from src.backends.sherpa_backend import SherpaBackend

    with profile_step("Create backend"):
        backend = SherpaBackend(model_size="giga-am-v2-ru")

    with profile_step("Load model"):
        backend.load_model()

    with profile_step("Transcribe (cold)"):
        text1, t1 = backend.transcribe(audio, sample_rate)

    with profile_step("Transcribe (warm)"):
        text2, t2 = backend.transcribe(audio, sample_rate)

    with profile_step("Transcribe (warm 2)"):
        text3, t3 = backend.transcribe(audio, sample_rate)

    print(f"\n  Backend times: {t1:.3f}s, {t2:.3f}s, {t3:.3f}s")
    print(f"  Threads used: {backend.num_threads}")

    # ============================================
    # Test 2: EnhancedTextProcessor
    # ============================================
    print("\n" + "=" * 60)
    print("TEST 2: EnhancedTextProcessor")
    print("=" * 60)

    with profile_step("Import EnhancedTextProcessor"):
        from src.text_processor_enhanced import EnhancedTextProcessor

    with profile_step("Create processor (no punctuation)"):
        proc1 = EnhancedTextProcessor(enable_punctuation=False)

    test_text = "привет это тестовый текст для проверки скорости обработки текста после транскрибации"

    with profile_step("Process text (no punctuation)"):
        result1 = proc1.process(test_text)

    with profile_step("Create processor (with punctuation)"):
        proc2 = EnhancedTextProcessor(enable_punctuation=True)

    with profile_step("Process text (1st call - loads model)"):
        result2 = proc2.process(test_text)

    with profile_step("Process text (2nd call - cached)"):
        result3 = proc2.process(test_text)

    with profile_step("Process text (3rd call - cached)"):
        result4 = proc2.process(test_text)

    # ============================================
    # Test 3: Full Transcriber Pipeline
    # ============================================
    print("\n" + "=" * 60)
    print("TEST 3: Full Transcriber (Sherpa + post-processing)")
    print("=" * 60)

    with profile_step("Import Transcriber"):
        from src.transcriber import Transcriber

    with profile_step("Create Transcriber (sherpa)"):
        transcriber = Transcriber(backend="sherpa", model_size="giga-am-v2-ru")

    with profile_step("Transcribe (cold)"):
        text_full1, time_full1 = transcriber.transcribe(audio, sample_rate)

    with profile_step("Transcribe (warm)"):
        text_full2, time_full2 = transcriber.transcribe(audio, sample_rate)

    with profile_step("Transcribe (warm 2)"):
        text_full3, time_full3 = transcriber.transcribe(audio, sample_rate)

    print(f"\n  Full pipeline times: {time_full1:.3f}s, {time_full2:.3f}s, {time_full3:.3f}s")

    # ============================================
    # Test 4: Compare with Whisper (if available)
    # ============================================
    print("\n" + "=" * 60)
    print("TEST 4: WhisperBackend (для сравнения)")
    print("=" * 60)

    try:
        with profile_step("Import WhisperBackend"):
            from src.backends.whisper_backend import WhisperBackend

        with profile_step("Create backend (base)"):
            whisper = WhisperBackend(model_size="base")

        with profile_step("Load model"):
            whisper.load_model()

        with profile_step("Transcribe (cold)"):
            tw1, tt1 = whisper.transcribe(audio, sample_rate)

        with profile_step("Transcribe (warm)"):
            tw2, tt2 = whisper.transcribe(audio, sample_rate)

        print(f"\n  Whisper times: {tt1:.3f}s, {tt2:.3f}s")

    except Exception as e:
        print(f"  Whisper not available: {e}")

    # ============================================
    # Summary
    # ============================================
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Sherpa raw transcription: {t2:.3f}s for {duration}s audio ({duration/t2:.1f}x realtime)")
    print(f"Full pipeline: {time_full2:.3f}s for {duration}s audio ({duration/time_full2:.1f}x realtime)")
    print(f"Post-processing overhead: {time_full2 - t2:.3f}s")


if __name__ == "__main__":
    main()
