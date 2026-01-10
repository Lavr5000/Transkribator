"""Mouse button handler for recording control."""
import threading
from typing import Callable, Optional

try:
    from pynput import mouse
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False


class MouseButtonHandler:
    """Handles global mouse button clicks for recording control."""

    def __init__(self, button: str = "middle", on_click: Optional[Callable] = None):
        """
        Initialize mouse button handler.

        Args:
            button: Button to use (left, middle, right, x1, x2)
            on_click: Callback when button is clicked
        """
        self.button = button
        self.on_click = on_click
        self._listener = None
        self._running = False
        self._lock = threading.Lock()
        self._last_click_time = 0
        self._debounce_ms = 200  # Prevent double-clicks

    def _get_button_enum(self):
        """Convert button string to pynput Button enum."""
        if not PYNPUT_AVAILABLE:
            return None

        button_map = {
            "left": mouse.Button.left,
            "middle": mouse.Button.middle,
            "right": mouse.Button.right,
            "x1": mouse.Button.x1,
            "x2": mouse.Button.x2,
        }
        return button_map.get(self.button)

    def _on_press(self, x, y, button, pressed):
        """Handle mouse button press."""
        import time

        if not pressed:
            return

        # Check if this is the configured button
        target_button = self._get_button_enum()
        if target_button is None or button != target_button:
            return

        # Debounce: prevent rapid double-clicks
        current_time = time.time() * 1000
        if current_time - self._last_click_time < self._debounce_ms:
            return

        self._last_click_time = current_time

        # Trigger callback in a separate thread to avoid blocking
        if self.on_click:
            threading.Thread(target=self.on_click, daemon=True).start()

    def start(self):
        """Start listening for mouse button clicks."""
        if not PYNPUT_AVAILABLE:
            raise RuntimeError("pynput not installed. Run: pip install pynput")

        with self._lock:
            if self._running:
                return

            self._running = True
            self._listener = mouse.Listener(
                on_click=self._on_press
            )
            self._listener.start()

    def stop(self):
        """Stop listening for mouse button clicks."""
        with self._lock:
            if not self._running:
                return

            self._running = False

            if self._listener:
                self._listener.stop()
                self._listener = None

    def is_running(self) -> bool:
        """Check if handler is running."""
        return self._running
