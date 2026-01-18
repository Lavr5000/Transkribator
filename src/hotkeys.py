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
        # Convert both sets to comparable format (use hash or special comparison)
        pressed_set = {self._key_to_compare(k) for k in self._pressed_keys}
        hotkey_set = {self._key_to_compare(k) for k in self._pynput_hotkey}

        if hotkey_set.issubset(pressed_set):
            self._on_hotkey_pressed()

    def _key_to_compare(self, key):
        """Convert key to comparable format."""
        from pynput import keyboard as pk
        # For KeyCode, use the char/value
        if isinstance(key, pk.KeyCode):
            return ('KeyCode', key.char, key.vk)
        # For special keys, use the name
        elif isinstance(key, pk.Key):
            return ('Key', str(key))
        return key

    def _on_key_release_pynput(self, key):
        """Handle key release for pynput."""
        # Remove key by comparing values, not objects
        to_remove = None
        key_comp = self._key_to_compare(key)
        for k in self._pressed_keys:
            if self._key_to_compare(k) == key_comp:
                to_remove = k
                break
        if to_remove:
            self._pressed_keys.discard(to_remove)

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
    WARNING: This can crash terminal apps like Claude Code!
    Consider using paste_from_clipboard() instead.

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


def paste_from_clipboard(use_terminal_shortcut: bool = True) -> bool:
    """
    Simulate paste keyboard shortcut (Ctrl+V or Ctrl+Shift+V for terminals).
    This is SAFER than type_text() for terminal apps like Claude Code.

    The text should already be in clipboard before calling this.

    Args:
        use_terminal_shortcut: If True, uses Ctrl+Shift+V (terminal paste),
                              otherwise uses Ctrl+V (standard paste)

    Returns:
        True if paste simulation was successful
    """
    import time

    if HOTKEY_BACKEND == "keyboard":
        try:
            if use_terminal_shortcut:
                # Terminal paste: Ctrl+Shift+V
                keyboard.press_and_release('ctrl+shift+v')
            else:
                # Standard paste: Ctrl+V
                keyboard.press_and_release('ctrl+v')
            return True
        except Exception as e:
            print(f"Failed to simulate paste: {e}")
            return False

    elif HOTKEY_BACKEND == "pynput":
        try:
            from pynput.keyboard import Controller, Key
            kb = Controller()

            if use_terminal_shortcut:
                # Terminal paste: Ctrl+Shift+V
                with kb.pressed(Key.ctrl):
                    with kb.pressed(Key.shift):
                        kb.press('v')
                        time.sleep(0.05)
                        kb.release('v')
            else:
                # Standard paste: Ctrl+V
                with kb.pressed(Key.ctrl):
                    kb.press('v')
                    time.sleep(0.05)
                    kb.release('v')
            return True
        except Exception as e:
            print(f"Failed to simulate paste: {e}")
            return False

    return False


def safe_paste_text(text: str, use_terminal_shortcut: bool = True, delay_before_paste: float = 0.1) -> bool:
    """
    Safely paste text by copying to clipboard first, then simulating paste shortcut.
    This is the RECOMMENDED method for pasting into terminal apps like Claude Code.

    Args:
        text: Text to paste
        use_terminal_shortcut: If True, uses Ctrl+Shift+V (terminal), else Ctrl+V
        delay_before_paste: Delay in seconds before simulating paste (allows focus settling)

    Returns:
        True if operation was successful
    """
    import time

    try:
        import pyperclip
        # Copy text to clipboard
        pyperclip.copy(text)

        # Small delay to ensure clipboard is ready and window focus is stable
        if delay_before_paste > 0:
            time.sleep(delay_before_paste)

        # Simulate paste shortcut
        return paste_from_clipboard(use_terminal_shortcut)
    except ImportError:
        print("pyperclip not available, falling back to type_text")
        type_text(text)
        return True
    except Exception as e:
        print(f"Failed to safe paste: {e}")
        return False
