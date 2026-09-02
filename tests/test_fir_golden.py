"""Golden spectral test for the Stage-1 48k -> 16k FIR (PLAN.md D3).

Binding acceptance criteria measured here, all on the ACTUAL resampler output
(not on the tap array alone):

  1. tap digest matches the checked-in SHA-256 (guards silent coefficient edits)
  2. taps <= 201
  3. passband flat to >= 7000 Hz within -1 dB
  4. folded alias energy: every input tone from 8000 Hz to just under 24000 Hz
     lands >= 60 dB below full scale ANYWHERE in the 0-8000 Hz output
  5. no scipy at runtime

Criterion 4 is the point of the test: after decimation, an input at f > 8 kHz
folds to |f - k*16000| and would otherwise be invisible to a single-tone check
at one frequency.
"""

import hashlib
import re
import time
from pathlib import Path

import numpy as np
import pytest

from src.fir_taps_48to16 import DECIM, FS_IN, FS_OUT, TAPS, TAPS_SHA256
from src.resampler import resample_48k_to_16k

SRC_DIR = Path(__file__).resolve().parents[1] / "src"

MAX_TAPS = 201
PASSBAND_HZ = 7000.0
STOPBAND_HZ = 8000.0
STOPBAND_DB = 60.0
PASSBAND_RIPPLE_DB = 1.0

TONE_SEC = 0.5
# Skip filter start-up/tail transients before measuring steady state.
SETTLE_OUT = len(TAPS) // DECIM + 8


def _tone(freq_hz, seconds=TONE_SEC, amp=1.0):
    n = int(FS_IN * seconds)
    t = np.arange(n, dtype=np.float64) / FS_IN
    return (amp * np.sin(2 * np.pi * freq_hz * t)).astype(np.float32)


def _steady_state(out):
    core = out[SETTLE_OUT:-SETTLE_OUT] if len(out) > 2 * SETTLE_OUT else out
    assert len(core) > 64, "steady-state window too short to measure"
    return core


def _level_db(out, amp=1.0):
    """Peak spectral level of the output, dB relative to a full-scale sine."""
    core = _steady_state(out)
    win = np.hanning(len(core))
    spec = np.abs(np.fft.rfft(core * win))
    # Full-scale reference measured the same way: a sine of amplitude `amp`
    # through the same window has peak magnitude amp * sum(win) / 4 * 2.
    ref = amp * win.sum() / 2.0
    return 20 * np.log10(max(spec.max(), 1e-20) / ref)


def test_tap_digest_and_count():
    digest = hashlib.sha256(np.asarray(TAPS, dtype="<f8").tobytes()).hexdigest()
    assert digest == TAPS_SHA256, (
        "FIR taps changed without regenerating the digest — rerun "
        "tasks/design_fir_48to16.py --write"
    )
    assert len(TAPS) <= MAX_TAPS, f"{len(TAPS)} taps exceeds the {MAX_TAPS} cap"
    assert len(TAPS) % 2 == 1, "odd tap count required for exact linear phase"
    assert abs(TAPS.sum() - 1.0) < 1e-12, "DC gain must be exactly 1.0"


def test_no_scipy_at_runtime():
    """scipy is a design-time dependency only (R12: +67.3 MB RSS)."""
    for name in ("resampler.py", "fir_taps_48to16.py"):
        text = (SRC_DIR / name).read_text(encoding="utf-8")
        code = "\n".join(
            line for line in text.splitlines() if not line.lstrip().startswith("#")
        )
        assert not re.search(r"^\s*(import|from)\s+scipy", code, re.M), (
            f"src/{name} must not import scipy at runtime"
        )


@pytest.mark.parametrize(
    "freq",
    [100.0, 300.0, 1000.0, 2000.0, 3400.0, 5000.0, 6000.0, 6500.0, 7000.0],
)
def test_passband_flat_within_1db(freq):
    out = resample_48k_to_16k(_tone(freq))
    level = _level_db(out)
    assert -PASSBAND_RIPPLE_DB <= level <= PASSBAND_RIPPLE_DB, (
        f"{freq:.0f} Hz passband level {level:+.2f} dB outside "
        f"+/-{PASSBAND_RIPPLE_DB} dB"
    )


def test_folded_alias_energy_across_full_stopband():
    """Sweep 8000 Hz -> input Nyquist; nothing may fold back above -60 dB."""
    freqs = np.arange(STOPBAND_HZ, FS_IN / 2.0, 50.0)
    worst_db, worst_f = -np.inf, None
    for f in freqs:
        level = _level_db(resample_48k_to_16k(_tone(float(f))))
        if level > worst_db:
            worst_db, worst_f = level, float(f)
    assert worst_db <= -STOPBAND_DB, (
        f"folded alias {worst_db:.2f} dB at {worst_f:.0f} Hz input exceeds "
        f"-{STOPBAND_DB:.0f} dB"
    )


def test_length_phase_and_dtype():
    x = np.zeros(48000, dtype=np.float32)
    x[24000] = 1.0  # impulse at a multiple of DECIM -> lands on an output sample
    out = resample_48k_to_16k(x)
    assert out.dtype == np.float32
    assert len(out) == 48000 // DECIM
    assert int(np.argmax(np.abs(out))) == 24000 // DECIM, "group delay not compensated"

    # (n, 1) chunk contract preserved, odd lengths rounded up.
    out2d = resample_48k_to_16k(np.zeros((48001, 1), dtype=np.float32))
    assert out2d.shape == (16001, 1)
    assert resample_48k_to_16k(np.zeros((0, 1), dtype=np.float32)).shape == (0, 1)
    assert FS_IN // DECIM == FS_OUT


@pytest.mark.parametrize(
    "chunks",
    [
        [960] * 25,                     # steady WASAPI blocksize
        [960] * 12 + [1545],            # ragged last frame
        [1, 2, 3, 997, 999, 999],       # pathological boundaries
        [24000],                        # one big chunk
    ],
)
def test_streaming_equals_block_form(chunks):
    """The recorder resamples per frame while recording; the concatenation must
    equal the offline block resample bit-for-bit, for any chunk boundaries."""
    from src.resampler import StreamingResampler

    rng = np.random.default_rng(7)
    total = sum(chunks)
    x = rng.standard_normal(total).astype(np.float32)
    ref = resample_48k_to_16k(x)

    sr, parts, i = StreamingResampler(), [], 0
    for c in chunks:
        parts.append(sr.process(x[i:i + c]))
        i += c
    parts.append(sr.finalize())
    got = np.concatenate(parts)

    assert got.shape == ref.shape
    assert np.abs(got - ref).max() == 0.0


def test_streaming_tail_flush_is_cheap():
    """stop() only flushes the tail — that must not scale with recording
    length, otherwise the +250 ms end-to-end budget breaks on long dictations."""
    from src.resampler import StreamingResampler

    sr = StreamingResampler()
    frame = _tone(440.0, seconds=0.02)  # 960 samples @48k
    for _ in range(int(60 / 0.02)):     # a minute of audio, frame by frame
        sr.process(frame)
    t0 = time.perf_counter()
    sr.finalize()
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.02, f"tail flush took {elapsed * 1000:.1f} ms"


def test_resample_speed_budget():
    """~55 ms per minute of audio expected (R12); assert a loose ceiling only."""
    audio = _tone(1000.0, seconds=60.0)
    t0 = time.perf_counter()
    resample_48k_to_16k(audio)
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.5, f"60 s of audio resampled in {elapsed * 1000:.0f} ms"
