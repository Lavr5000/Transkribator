"""48 kHz -> 16 kHz decimation with a precomputed Kaiser FIR (Stage 1, D3).

Pure numpy on purpose: importing scipy at runtime costs +67.3 MB RSS (R12).
Taps live in `fir_taps_48to16.py` and are generated on the dev side by
`tasks/design_fir_48to16.py`; `tests/test_fir_golden.py` guards both the tap
digest and the measured spectral behaviour.

Runs once over a finished recording in the stop() worker, never in the audio
callback.
"""

from typing import Optional

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from .fir_taps_48to16 import DECIM, FS_IN, FS_OUT, TAPS

__all__ = ["resample_48k_to_16k", "StreamingResampler", "resample_if_needed",
           "DECIM", "FS_IN", "FS_OUT"]

# Linear-phase odd-length FIR -> integer group delay, compensated by centring
# the analysis window on each output sample.
_GROUP_DELAY = (len(TAPS) - 1) // 2
_TAPS_REV = np.ascontiguousarray(TAPS[::-1])
# ponytail: fixed 8192-output block (~13 MB of float64 windows) keeps peak memory
# flat for any recording length; tune only if profiling says the matmul is starved.
_BLOCK = 8192


def resample_48k_to_16k(audio: np.ndarray) -> np.ndarray:
    """Anti-alias filter and decimate 48 kHz mono audio to 16 kHz.

    Accepts shape (n,) or (n, 1) float arrays; returns float32 of shape (m, 1)
    when given (n, 1) and (m,) when given (n,), so callers keep their chunk
    contract. Output length is ceil(n / DECIM), phase-aligned with the input
    (output sample k corresponds to input sample k * DECIM).
    """
    if audio is None:
        return audio
    arr = np.asarray(audio)
    was_2d = arr.ndim == 2
    if was_2d:
        if arr.shape[1] != 1:
            raise ValueError(f"expected mono (n, 1), got {arr.shape}")
        arr = arr[:, 0]
    elif arr.ndim != 1:
        raise ValueError(f"expected 1-D or (n, 1) audio, got shape {arr.shape}")

    x = np.ascontiguousarray(arr, dtype=np.float64)
    n_out = -(-len(x) // DECIM)  # ceil
    if n_out == 0:
        out = np.zeros(0, dtype=np.float32)
        return out[:, None] if was_2d else out

    # Zero-pad so every output sample has a full centred window. The filter is
    # applied in reversed-tap correlation form, hence _TAPS_REV below.
    total = max((n_out - 1) * DECIM + len(TAPS), _GROUP_DELAY + len(x))
    padded = np.zeros(total, dtype=np.float64)
    padded[_GROUP_DELAY:_GROUP_DELAY + len(x)] = x

    # Only every DECIM-th window is materialised (polyphase in effect), so the
    # two discarded outputs per input triple are never computed. Blocked so the
    # window matrix stays a few MB regardless of recording length (R12: the
    # resample step must not move RSS).
    windows = sliding_window_view(padded, len(TAPS))[: n_out * DECIM : DECIM]
    out = np.empty(n_out, dtype=np.float64)
    for lo in range(0, n_out, _BLOCK):
        hi = min(lo + _BLOCK, n_out)
        np.matmul(windows[lo:hi], _TAPS_REV, out=out[lo:hi])

    out = out.astype(np.float32, copy=False)
    return out[:, None] if was_2d else out


class StreamingResampler:
    """Same filter, fed chunk by chunk while the recording is still running.

    Why: the block form costs ~125 ms per minute of audio (197 taps, measured
    2026-07-30), so at the p95 utterance length of ~4.6 min a resample at
    stop() would add ~570 ms and blow the +250 ms end-to-end latency budget on
    its own. Fed from the collector thread instead, the work overlaps with
    recording and stop() only has to flush the tail.

    Output is sample-for-sample identical to resample_48k_to_16k() over the
    same total input, for any chunk boundaries (guarded by a test).
    """

    def __init__(self):
        # Leading zeros so output sample 0 sees the same padded window the
        # block form gives it.
        self._buf = np.zeros(_GROUP_DELAY, dtype=np.float64)
        self._base = -_GROUP_DELAY   # absolute input index of self._buf[0]
        self._next_n = 0             # next output sample index to emit

    def process(self, chunk: np.ndarray) -> np.ndarray:
        """Feed input samples, get whatever output is fully determined."""
        arr = np.asarray(chunk)
        was_2d = arr.ndim == 2
        if was_2d:
            arr = arr[:, 0]
        self._buf = np.concatenate([self._buf, np.asarray(arr, dtype=np.float64)])

        # Output n needs input up to n*DECIM + _GROUP_DELAY.
        last_avail = self._base + len(self._buf) - 1
        n_last = (last_avail - _GROUP_DELAY) // DECIM
        out = self._emit(self._next_n, n_last)
        self._trim()
        return out[:, None] if was_2d else out

    def finalize(self) -> np.ndarray:
        """Flush the tail with zero padding; equals the block form's last
        samples. The resampler is unusable afterwards until reset()."""
        n_total = -(-(self._base + len(self._buf)) // DECIM)
        need = (n_total - 1) * DECIM + _GROUP_DELAY - (self._base + len(self._buf) - 1)
        if need > 0:
            self._buf = np.concatenate([self._buf, np.zeros(need, dtype=np.float64)])
        out = self._emit(self._next_n, n_total - 1)
        self._trim()
        return out

    def reset(self) -> None:
        self.__init__()

    def _emit(self, n_from: int, n_to: int) -> np.ndarray:
        if n_to < n_from:
            return np.zeros(0, dtype=np.float32)
        count = n_to - n_from + 1
        start = n_from * DECIM - _GROUP_DELAY - self._base
        if start < 0:
            return np.zeros(0, dtype=np.float32)
        window_span = (count - 1) * DECIM + len(TAPS)
        if start + window_span > len(self._buf):
            return np.zeros(0, dtype=np.float32)
        windows = sliding_window_view(self._buf[start:start + window_span], len(TAPS))[::DECIM]
        out = np.empty(count, dtype=np.float64)
        for lo in range(0, count, _BLOCK):
            hi = min(lo + _BLOCK, count)
            np.matmul(windows[lo:hi], _TAPS_REV, out=out[lo:hi])
        self._next_n = n_to + 1
        return out.astype(np.float32, copy=False)

    def _trim(self) -> None:
        """Drop input the remaining outputs can no longer reach."""
        keep_from_abs = self._next_n * DECIM - _GROUP_DELAY
        drop = keep_from_abs - self._base
        if drop > 0:
            self._buf = self._buf[drop:].copy()
            self._base = keep_from_abs


def resample_if_needed(audio: np.ndarray, in_rate: int, out_rate: int = FS_OUT) -> Optional[np.ndarray]:
    """Pass-through unless the rates are exactly the 48k -> 16k pair we support."""
    if audio is None or in_rate == out_rate:
        return audio
    if in_rate == FS_IN and out_rate == FS_OUT:
        return resample_48k_to_16k(audio)
    raise ValueError(f"unsupported resample {in_rate} -> {out_rate}")
