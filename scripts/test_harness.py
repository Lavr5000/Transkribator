"""E2E test harness for Transkribator — verifies the app works without a human voice.

Modes:
  --health    Device probe: stream open latency, callback rate, signal RMS.
              Detects the "opens but delivers zero frames" driver failure.
  --pipeline  Known Russian phrase (Windows SAPI TTS WAV) -> Transcriber ->
              fuzzy text match. No microphone involved: tests the
              transcription pipeline end-to-end.
  --acoustic  Plays the TTS phrase through the SPEAKERS and records it with
              the real MICROPHONE via the app's AudioRecorder (persistent
              stream), then transcribes and fuzzy-matches. Full hardware loop
              - the closest thing to a human test. Requires speakers on.
  --all       health -> pipeline -> acoustic (stops early if health = DEAD).

Usage:
  python scripts/test_harness.py --all
  python scripts/test_harness.py --health
  python scripts/test_harness.py --pipeline --backend sherpa
"""
import argparse
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np

PHRASE = "Сегодня хорошая погода и мы проверяем работу программы для распознавания речи"
PHRASE_WORDS = set(PHRASE.lower().split())
MATCH_THRESHOLD = 0.6  # >=60% of phrase words must appear in the transcript


def log(msg):
    print(msg, flush=True)


def verdict(name, ok, detail=""):
    log(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return ok


# --------------------------------------------------------------------- #
# health                                                                 #
# --------------------------------------------------------------------- #

def run_health():
    log("=== HEALTH: microphone device probe")
    import sounddevice as sd

    frames = [0]
    rms_acc = []

    def cb(indata, f, t, s):
        frames[0] += 1
        rms_acc.append(float(np.sqrt(np.mean(indata ** 2))))

    t0 = time.monotonic()
    try:
        stream = sd.InputStream(samplerate=16000, channels=1, dtype=np.float32,
                                blocksize=1024, callback=cb)
    except Exception as e:
        return verdict("health", False, f"open failed: {type(e).__name__}: {e}")
    open_s = time.monotonic() - t0
    stream.start()
    time.sleep(2.0)
    n = frames[0]
    rms = max(rms_acc) if rms_acc else 0.0
    t0 = time.monotonic()
    stream.stop()
    stream.close()
    close_s = time.monotonic() - t0

    log(f"  open={open_s:.1f}s close={close_s:.1f}s callbacks/2s={n} (expect ~31) max_rms={rms:.4f}")
    if n == 0:
        return verdict("health", False,
                       "DEAD: stream opens but delivers ZERO frames (driver wedged — reboot)")
    if open_s > 3.0:
        verdict("health", True, f"DEGRADED: open takes {open_s:.1f}s (persistent stream absorbs this)")
        return True
    return verdict("health", True, "device OK")


# --------------------------------------------------------------------- #
# TTS reference audio                                                    #
# --------------------------------------------------------------------- #

def make_tts_wav() -> Path:
    """Generate the known Russian phrase via Windows SAPI -> 16kHz mono WAV."""
    out = Path(tempfile.gettempdir()) / "transkribator_harness_phrase.wav"
    ps = f'''
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$ru = $s.GetInstalledVoices() | Where-Object {{ $_.VoiceInfo.Culture.Name -like "ru*" }} | Select-Object -First 1
if (-not $ru) {{ Write-Error "NO_RUSSIAN_VOICE"; exit 2 }}
$s.SelectVoice($ru.VoiceInfo.Name)
$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$s.SetOutputToWaveFile("{out}", $fmt)
$s.Speak("{PHRASE}")
$s.Dispose()
Write-Output "OK"
'''
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, text=True, timeout=60)
    if "OK" not in r.stdout or not out.exists():
        raise RuntimeError(f"SAPI TTS failed: {r.stdout} {r.stderr}")
    return out


def load_wav_16k(path: Path) -> np.ndarray:
    import soundfile as sf
    data, sr = sf.read(str(path), dtype="float32")
    if data.ndim > 1:
        data = data[:, 0]
    if sr != 16000:
        # naive linear resample — fine for a harness
        n = int(len(data) * 16000 / sr)
        data = np.interp(np.linspace(0, len(data) - 1, n), np.arange(len(data)), data).astype(np.float32)
    return data


def match_score(text: str) -> float:
    got = set("".join(ch if ch.isalnum() or ch.isspace() else " " for ch in text.lower()).split())
    if not PHRASE_WORDS:
        return 0.0
    return len(PHRASE_WORDS & got) / len(PHRASE_WORDS)


def make_transcriber(backend: str):
    from src.transcriber import Transcriber
    if backend == "sherpa":
        return Transcriber(backend="sherpa", model_size="giga-am-v3-ru-punct",
                           device="cpu", compute_type="int8", language="ru")
    from src.config import Config
    cfg = Config.load()
    return Transcriber(backend=cfg.backend, model_size=cfg.model_size,
                       device=cfg.device, compute_type=cfg.compute_type, language=cfg.language)


# --------------------------------------------------------------------- #
# pipeline                                                               #
# --------------------------------------------------------------------- #

def run_pipeline(backend: str):
    log("=== PIPELINE: TTS WAV -> Transcriber -> text match (no mic)")
    wav = make_tts_wav()
    audio = load_wav_16k(wav)
    log(f"  reference audio: {len(audio)/16000:.1f}s")
    tr = make_transcriber(backend)
    t0 = time.monotonic()
    text = tr.transcribe(audio, sample_rate=16000)
    if isinstance(text, tuple):
        text = text[0]
    score = match_score(text or "")
    log(f"  transcript ({time.monotonic()-t0:.1f}s): {text!r}")
    log(f"  word match: {score:.0%} (threshold {MATCH_THRESHOLD:.0%})")
    return verdict("pipeline", score >= MATCH_THRESHOLD)


# --------------------------------------------------------------------- #
# acoustic                                                               #
# --------------------------------------------------------------------- #

def run_acoustic(backend: str):
    log("=== ACOUSTIC: speakers -> real mic (AudioRecorder) -> Transcriber")
    import sounddevice as sd
    from src.audio_recorder import AudioRecorder

    wav = make_tts_wav()
    audio_ref = load_wav_16k(wav)

    rec = AudioRecorder(sample_rate=16000, channels=1, webrtc_enabled=True)
    log("  opening persistent stream (may take 25s+ on a degraded stack)...")
    if not rec.open_stream():
        return verdict("acoustic", False, "open_stream failed")
    time.sleep(0.5)

    status = rec.start()
    if status != "started":
        rec.close_stream()
        return verdict("acoustic", False, f"recorder.start() -> {status}")

    log(f"  playing phrase through speakers ({len(audio_ref)/16000:.1f}s)...")
    sd.play(audio_ref, samplerate=16000, blocking=True)
    time.sleep(0.5)

    captured = rec.stop()
    degraded = rec.capture_degraded
    rec.close_stream()

    if captured is None or len(captured) == 0:
        return verdict("acoustic", False, "captured ZERO audio from mic")
    rms = float(np.sqrt(np.mean(captured ** 2)))
    log(f"  captured {len(captured)/16000:.1f}s, rms={rms:.4f}, degraded={degraded}")
    if rms < 0.001:
        return verdict("acoustic", False, "mic captured silence — speakers off or mic dead")

    tr = make_transcriber(backend)
    text = tr.transcribe(captured.flatten(), sample_rate=16000)
    if isinstance(text, tuple):
        text = text[0]
    score = match_score(text or "")
    log(f"  transcript: {text!r}")
    log(f"  word match: {score:.0%} (threshold {MATCH_THRESHOLD:.0%})")
    return verdict("acoustic", score >= MATCH_THRESHOLD and not degraded)


# --------------------------------------------------------------------- #

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--health", action="store_true")
    p.add_argument("--pipeline", action="store_true")
    p.add_argument("--acoustic", action="store_true")
    p.add_argument("--all", action="store_true")
    p.add_argument("--backend", default="sherpa", choices=["sherpa", "config"],
                   help="sherpa = local offline model; config = whatever config.json says (e.g. groq)")
    args = p.parse_args()

    results = {}
    if args.all or args.health:
        results["health"] = run_health()
        if args.all and not results["health"]:
            log("Health FAIL — skipping pipeline/acoustic (device unusable).")
            sys.exit(1)
    if args.all or args.pipeline:
        results["pipeline"] = run_pipeline(args.backend)
    if args.all or args.acoustic:
        results["acoustic"] = run_acoustic(args.backend)

    if not results:
        p.print_help()
        sys.exit(2)

    log("=== SUMMARY: " + ", ".join(f"{k}={'PASS' if v else 'FAIL'}" for k, v in results.items()))
    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    main()
