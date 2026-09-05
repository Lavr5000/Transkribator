"""Unload the ASR model after a period without dictation.

The tray app used to keep GigaAM resident forever (~1.8 GB private bytes
even when nobody dictated for hours). Windows logged "low virtual memory"
events every day 31.08-03.09 with pythonw among the top consumers.
The model reloads lazily on the next transcribe() call (2-4 s), so the
cost of unloading is a slightly longer first "Обработка...".
"""
import logging
import threading
from typing import Callable

logger = logging.getLogger("transkribator")


class IdleUnloader:
    """Arm after each transcription; fire unload_fn when idle long enough.

    is_busy_fn guards against unloading under a live decode: if the app is
    recording or processing when the timer fires, the timer is simply re-armed.
    """

    def __init__(self, timeout_s: float, unload_fn: Callable[[], None],
                 is_busy_fn: Callable[[], bool]):
        self.timeout_s = float(timeout_s)
        self._unload = unload_fn
        self._is_busy = is_busy_fn
        self._timer = None
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self.timeout_s > 0

    def arm(self) -> None:
        """(Re)start the countdown. No-op when disabled."""
        if not self.enabled:
            return
        with self._lock:
            self._cancel_locked()
            self._timer = threading.Timer(self.timeout_s, self._fire)
            self._timer.daemon = True
            self._timer.name = "idle-unload"
            self._timer.start()

    def cancel(self) -> None:
        with self._lock:
            self._cancel_locked()

    def _cancel_locked(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def _fire(self) -> None:
        with self._lock:
            self._timer = None
        if self._is_busy():
            logger.debug("IDLE_UNLOAD_DEFERRED | busy at timeout, re-arming")
            self.arm()
            return
        try:
            self._unload()
            logger.info("IDLE_UNLOAD | model released after %.0fs idle", self.timeout_s)
        except Exception as e:  # never let a timer thread die loudly
            logger.warning("IDLE_UNLOAD_FAILED | %s", e)
