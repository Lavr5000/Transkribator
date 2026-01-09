"""Global hotkey management for WhisperTyping."""
import threading
from typing import Callable, Optional

# Try keyboard first (better cross-platform support), fallback to pynput
HOTKEY_BACKEND = None

try:
    import keyboard
    HOTKEY_BACKEND = "keyboard"
except ImportError:
    try:
        from pynput import keyboard as pynput_keyboard
        HOTKEY_BACKEND = "pynput"
    except ImportError:
        pass


class HotkeyManager:
    """Manages global hotkeys."""

    def __init__(self, on_hotkey: Optional[Callable[[], None]] = None):
        self.on_hotkey = on_hotkey
        self._hotkey = None
        self._listener = None
        self._running = False
        self._current_hotkey = ""

    def register(self, hotkey: str) -> bool:
        """
        Register a global hotkey.

        Args:
            hotkey: Hotkey string (e.g., "ctrl+shift+space", "F9", "`")

        Returns:
            True if registration successful
        """
        if HOTKEY_BACKEND is None:
            print("No hotkey backend available")
            return False

        # Unregister existing hotkey
        self.unregister()

        try:
            if HOTKEY_BACKEND == "keyboard":
                # Use keyboard library
                self._hotkey = keyboard.add_hotkey(
                    hotkey,
                    self._on_hotkey_pressed,
                    suppress=False
                )
                self._running = True
                self._current_hotkey = hotkey
                return True

            elif HOTKEY_BACKEND == "pynput":
                # Parse hotkey for pynput
                self._pynput_hotkey = self._parse_hotkey_pynput(hotkey)
                self._pressed_keys = set()

                self._listener = pynput_keyboard.Listener(
                    on_press=self._on_key_press_pynput,
                    on_release=self._on_key_release_pynput
                )
                self._listener.start()
                self._running = True
                self._current_hotkey = hotkey
                return True

        except Exception as e:
            print(f"Failed to register hotkey: {e}")
            return False

        return False

    def _parse_hotkey_pynput(self, hotkey: str) -> set:
        """Parse hotkey string for pynput."""
        from pynput import keyboard as pk

        key_map = {
            'ctrl': pk.Key.ctrl,
            'control': pk.Key.ctrl,
            'shift': pk.Key.shift,
            'alt': pk.Key.alt,
            'cmd': pk.Key.cmd,
            'super': pk.Key.cmd,
            'win': pk.Key.cmd,
            'space': pk.Key.space,
            'enter': pk.Key.enter,
            'return': pk.Key.enter,
            'tab': pk.Key.tab,
            'esc': pk.Key.esc,
            'escape': pk.Key.esc,
            'backspace': pk.Key.backspace,
            'delete': pk.Key.delete,
            'up': pk.Key.up,
            'down': pk.Key.down,
            'left': pk.Key.left,
            'right': pk.Key.right,
            '`': pk.KeyCode.from_char('`'),
            '~': pk.KeyCode.from_char('~'),
        }

        # Add function keys
        for i in range(1, 13):
            key_map[f'f{i}'] = getattr(pk.Key, f'f{i}')

        keys = set()
        for part in hotkey.lower().replace('+', ' ').split():
            part = part.strip()
            if part in key_map:
                keys.add(key_map[part])
            elif len(part) == 1:
                keys.add(pk.KeyCode.from_char(part))

        return keys

    def _on_key_press_pynput(self, key):
        """Handle key press for pynput."""
        self._pressed_keys.add(key)

        # Check if hotkey combination is pressed
        if self._pynput_hotkey.issubset(self._pressed_keys):
            self._on_hotkey_pressed()

    def _on_key_release_pynput(self, key):
        """Handle key release for pynput."""
        self._pressed_keys.discard(key)

    def _on_hotkey_pressed(self):
        """Called when hotkey is pressed."""
        if self.on_hotkey:
            # Run callback in separate thread to avoid blocking
            threading.Thread(target=self.on_hotkey, daemon=True).start()

    def unregister(self) -> None:
        """Unregister the current hotkey."""
        self._running = False

        if HOTKEY_BACKEND == "keyboard" and self._hotkey is not None:
            try:
                keyboard.remove_hotkey(self._hotkey)
            except Exception:
                pass
            self._hotkey = None

        elif HOTKEY_BACKEND == "pynput" and self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None

        self._current_hotkey = ""

    @property
    def current_hotkey(self) -> str:
        """Get the currently registered hotkey."""
        return self._current_hotkey

    @property
    def is_running(self) -> bool:
        """Check if hotkey listener is running."""
        return self._running


def get_available_backend() -> Optional[str]:
    """Get the available hotkey backend."""
    return HOTKEY_BACKEND


def type_text(text: str, interval: float = 0.0) -> None:
    """
    Type text using keyboard simulation.

    Args:
        text: Text to type
        interval: Delay between keystrokes
    """
    if HOTKEY_BACKEND == "keyboard":
        try:
            keyboard.write(text, delay=interval)
        except Exception as e:
            print(f"Failed to type text: {e}")

    elif HOTKEY_BACKEND == "pynput":
        try:
            from pynput.keyboard import Controller
            kb = Controller()
            for char in text:
                kb.type(char)
                if interval > 0:
                    import time
                    time.sleep(interval)
        except Exception as e:
            print(f"Failed to type text: {e}")
