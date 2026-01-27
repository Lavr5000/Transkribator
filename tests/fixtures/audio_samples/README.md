# Audio Test Samples

This directory contains audio files for ASR quality testing.

## File Format

Each audio file should have a corresponding `.txt` file with the same name:

```
test.wav          # Audio sample (16kHz, mono)
test.wav.txt      # Reference transcription (Russian)
```

## Adding Test Samples

1. Place audio file in this directory (WAV or MP3, 16kHz mono recommended)
2. Create matching `.txt` file with exact transcription
3. Run: `python tests/test_backend_quality.py`

## Recommended Samples

- Short phrase (5-10 seconds): Quick iteration test
- Medium sentence (15-30 seconds): Real-world usage
- Long text (60+ seconds): Stability test
- Noisy audio: VAD effectiveness test
- Quiet audio: Hallucination detection test

## Example

```
poem.wav          # Recording of Russian poem
poem.wav.txt      # Exact text: "И тропинка, и лесок, В поле – каждый колосок!"
```
