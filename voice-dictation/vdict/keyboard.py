"""
Module: keyboard.py
Purpose: Keyboard event injection and PTT button monitoring

Responsibilities:
  - Listen for middle mouse button (or other PTT trigger)
  - Inject transcribed text at cursor position
  - Platform-specific keyboard/mouse event handling
"""

import threading
from pynput import mouse, keyboard

# Mouse button names accepted in config.json -> pynput button enum.
# "side" maps to x2 (commonly the "forward" side button on a mouse) since
# side buttons aren't globally hooked by Windows the way middle-click
# autoscroll is in browsers/Electron apps.
_BUTTON_MAP = {
    "left": mouse.Button.left,
    "right": mouse.Button.right,
    "middle": mouse.Button.middle,
    "side": mouse.Button.x2,
    "x1": mouse.Button.x1,
    "x2": mouse.Button.x2,
}


class PTTListener:
    """Push-to-talk trigger listener (configurable mouse button or keyboard key)"""

    def __init__(self, button="middle", debug=False):
        """
        Initialize PTT listener

        Args:
            button: Trigger to monitor. Either a mouse button name
                ("left", "right", "middle", "side", "x1", "x2") or a
                keyboard key using "key:<name>" (e.g. "key:f13"), where
                <name> matches a pynput.keyboard.Key member. Useful for
                gaming-mouse buttons remapped to send a keystroke instead
                of a native mouse-button signal.
            debug: Print debug messages for all events
        """
        self.button_name = button
        self.pressed = False
        self.debug = debug

        # Threading events for blocking waits
        self.press_event = threading.Event()
        self.release_event = threading.Event()

        if button.startswith("key:"):
            key_name = button[len("key:"):]
            self.target_key = getattr(keyboard.Key, key_name, None)
            if self.target_key is None:
                if len(key_name) == 1:
                    self.target_key = keyboard.KeyCode.from_char(key_name)
                else:
                    raise ValueError(f"Unsupported PTT key: '{key_name}'")
            self.button = None
            self.listener = keyboard.Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release)
        else:
            self.button = _BUTTON_MAP.get(button)
            if self.button is None:
                raise ValueError(
                    f"Unsupported PTT button: '{button}'. "
                    f"Supported: {list(_BUTTON_MAP)}")
            self.target_key = None
            self.listener = mouse.Listener(on_click=self._on_click)

        self.listener.start()

        if self.debug:
            print(f"[DEBUG] PTTListener started, monitoring: {self.button_name}")

    def _on_click(self, x, y, button, pressed):
        """
        Internal callback for mouse events (runs in background thread)

        Args:
            x, y: Mouse position (unused)
            button: Mouse button that triggered event
            pressed: True if pressed, False if released
        """
        if self.debug:
            print(f"[DEBUG] Mouse event: button={button}, "
                  f"pressed={pressed}, target={self.button}")

        if button == self.button:
            self.pressed = pressed
            if pressed:
                if self.debug:
                    print("[DEBUG] Target button PRESSED - setting event")
                self.press_event.set()
                self.release_event.clear()
            else:
                if self.debug:
                    print("[DEBUG] Target button RELEASED - setting event")
                self.release_event.set()
                self.press_event.clear()

    def _on_key_press(self, key):
        """Internal callback for keyboard press events (runs in background thread)"""
        if self.debug:
            print(f"[DEBUG] Key event: key={key}, target={self.target_key}")

        if key == self.target_key and not self.pressed:
            self.pressed = True
            if self.debug:
                print("[DEBUG] Target key PRESSED - setting event")
            self.press_event.set()
            self.release_event.clear()

    def _on_key_release(self, key):
        """Internal callback for keyboard release events (runs in background thread)"""
        if key == self.target_key:
            self.pressed = False
            if self.debug:
                print("[DEBUG] Target key RELEASED - setting event")
            self.release_event.set()
            self.press_event.clear()

    def wait_for_press(self, timeout_secs=None):
        """
        Block until PTT button is pressed

        Args:
            timeout_secs: Maximum time to wait in seconds. None for infinite.

        Returns:
            bool: True if button pressed, False if timed out
        """
        import time
        start_time = time.time()

        while not self.press_event.wait(timeout=0.1):
            if timeout_secs is not None and (
                    time.time() - start_time) >= timeout_secs:
                return False
        return True

    def wait_for_release(self):
        """Block until PTT button is released"""
        while not self.release_event.wait(timeout=0.1):
            pass  # Loop allows KeyboardInterrupt to be raised

    def stop(self):
        """Stop mouse listener (cleanup)"""
        self.listener.stop()


class KeyboardInjector:
    """Text injection at cursor position via clipboard"""

    def __init__(self, preserve_clipboard=False):
        """Initialize keyboard injector"""
        self.preserve_clipboard = preserve_clipboard
        try:
            import pyperclip
            import pyautogui
            import time
            self.pyperclip = pyperclip
            self.pyautogui = pyautogui
            self.time = time
        except ImportError as e:
            raise RuntimeError(
                f"Missing dependency: {e}. "
                f"Install: pip install pyperclip pyautogui") from e

    def inject(self, text):
        """
        Inject text at current cursor position

        Uses clipboard method with save/restore:
        1. Save current clipboard
        2. Put text in clipboard
        3. Paste (Ctrl+V)
        4. Restore original clipboard after delay

        Args:
            text: Text to paste at cursor (space is appended for separation)
        """
        if not text or not text.strip():
            return  # Skip empty text

        # Save current clipboard
        try:
            old_clipboard = self.pyperclip.paste()
        except Exception:
            old_clipboard = ""  # Clipboard empty or inaccessible

        # Add space after text for separation, then paste
        self.pyperclip.copy(text + " ")
        self.pyautogui.hotkey('ctrl', 'v')

        # Wait for paste to complete, then conditionally restore clipboard
        self.time.sleep(0.05)  # 50ms delay

        if not self.preserve_clipboard:
            self.pyperclip.copy(old_clipboard)
