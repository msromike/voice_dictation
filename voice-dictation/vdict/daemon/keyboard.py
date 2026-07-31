"""PTT trigger monitoring and text injection at the cursor."""

import threading
from pynput import mouse, keyboard

# config.json name -> pynput button. "side" is x2: browsers hook middle-click,
# not that. Left is absent on purpose -- it would record on every click.
BUTTON_MAP = {
    "right": mouse.Button.right,
    "middle": mouse.Button.middle,
    "side": mouse.Button.x2,
    "x1": mouse.Button.x1,
    "x2": mouse.Button.x2,
}


class PTTListener:
    """Push-to-talk trigger listener (configurable mouse button or keyboard key)"""

    def __init__(self, button="middle"):
        """Start listening for the PTT trigger.
        button is a mouse name from BUTTON_MAP, or "key:<name>" for a pynput Key."""
        self.pressed = False

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
            self.button = BUTTON_MAP.get(button)
            if self.button is None:
                raise ValueError(
                    f"Unsupported PTT button: '{button}'. "
                    f"Supported: {list(BUTTON_MAP)}")
            self.target_key = None
            self.listener = mouse.Listener(on_click=self._on_click)

        self.listener.start()

    def _on_click(self, x, y, button, pressed):
        """Internal callback for mouse events. Runs on the pynput background thread."""
        if button == self.button:
            self.pressed = pressed
            if pressed:
                self.press_event.set()
                self.release_event.clear()
            else:
                self.release_event.set()
                self.press_event.clear()

    def _on_key_press(self, key):
        """Internal callback for keyboard press events (runs in background thread)"""
        if key == self.target_key and not self.pressed:
            self.pressed = True
            self.press_event.set()
            self.release_event.clear()

    def _on_key_release(self, key):
        """Internal callback for keyboard release events (runs in background thread)"""
        if key == self.target_key:
            self.pressed = False
            self.release_event.set()
            self.press_event.clear()

    def wait_for_press(self, timeout_secs=None):
        """Block until the PTT trigger is pressed, returning True.
        Returns False if timeout_secs elapses; None waits forever."""
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
        """Paste text at the cursor via the clipboard, appending a trailing space.
        Restores the previous clipboard unless preserve_clipboard is set."""
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
