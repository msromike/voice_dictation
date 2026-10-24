"""PTT trigger monitoring and text injection at the cursor."""

import ctypes
import struct
import threading
import time

import pyautogui
import pywintypes
import win32api
import win32clipboard
import win32con
import win32gui
from pynput import mouse, keyboard

from vdict.common.output import log

# pyautogui waits 0.1s after every call it makes. The paste receipt arrives while
# we pump messages, so that wait would only delay the restore.
pyautogui.PAUSE = 0

_user32 = ctypes.windll.user32
_user32.SetClipboardData.restype = ctypes.c_void_p
_user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]

# Windows' clipboard-history monitor asks for the text the instant it is announced,
# which would fire the receipt before any paste. MEASURED: this flag stops it.
_EXCLUDE_FORMAT = win32clipboard.RegisterClipboardFormat(
    "ExcludeClipboardContentFromMonitorProcessing")

# GDI handles. GetClipboardData hands back a handle that cannot be set back, and
# MEASURED: Windows re-synthesizes CF_BITMAP from the restored CF_DIB anyway.
_SKIP_FORMATS = frozenset({2, 3, 9, 14, 0x80, 0x82, 0x83, 0x8E})

# Nothing asked for the text: no text field focused, or an elevated window that
# ignores synthetic keys. A backstop, not a tuning constant -- the receipt ends the wait.
_RECEIPT_TIMEOUT = 1.0

# pynput key events carry no modifier state, and its Controller.modifiers holds
# only keys this app synthesised. Windows reports the physical state directly.
MODIFIER_VKS = (win32con.VK_SHIFT, win32con.VK_CONTROL, win32con.VK_MENU)

# config.json name -> pynput button. "side" is x2: browsers hook middle-click,
# not that. Left is absent on purpose -- it would record on every click.
BUTTON_MAP = {
    "right": mouse.Button.right,
    "middle": mouse.Button.middle,
    "side": mouse.Button.x2,
    "x1": mouse.Button.x1,
    "x2": mouse.Button.x2,
}


def _modifier_held():
    """True while Shift, Ctrl or Alt is physically down."""
    return any(win32api.GetAsyncKeyState(vk) & 0x8000 for vk in MODIFIER_VKS)


class PTTListener:
    """Push-to-talk trigger listener (configurable mouse button or keyboard key)"""

    def __init__(self, button="middle", *, on_enter):
        """Start listening for the PTT trigger. button is a BUTTON_MAP mouse name
        or "key:<name>"; on_enter(hwnd) fires on every unmodified Enter."""
        self.pressed = False
        self.on_enter = on_enter

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
            self.mouse_listener = None
        else:
            self.button = BUTTON_MAP.get(button)
            if self.button is None:
                raise ValueError(
                    f"Unsupported PTT button: '{button}'. "
                    f"Supported: {list(BUTTON_MAP)}")
            self.target_key = None
            self.mouse_listener = mouse.Listener(on_click=self._on_click)

        # Always on, whatever the PTT is -- Enter closes a dictation block.
        self.key_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release)

        self.key_listener.start()
        if self.mouse_listener is not None:
            self.mouse_listener.start()

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
        if key == keyboard.Key.enter and not _modifier_held():
            self.on_enter(win32gui.GetForegroundWindow())

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
        """Stop both listeners (cleanup)"""
        self.key_listener.stop()
        if self.mouse_listener is not None:
            self.mouse_listener.stop()


def _dropfiles(paths):
    """CF_HDROP reads back as a tuple of paths; writing it needs the struct rebuilt.
    20-byte header, then the paths UTF-16 and double-null terminated."""
    header = struct.pack("<Lllll", 20, 0, 0, 0, 1)
    return header + ("".join(p + "\0" for p in paths) + "\0").encode("utf-16-le")


class KeyboardInjector:
    """Text injection at cursor position via clipboard, with the clipboard put back"""

    def __init__(self):
        """Creates the hidden window Windows sends the paste receipt to. Clipboard
        calls stay on this thread, which is the daemon's capture loop."""
        self._text = ""
        self._served = threading.Event()
        # The stubs declare both as read-only properties (_win32typing.pyi:2477,
        # :2479); assigning them is how pywin32 registers a window class.
        cls = win32gui.WNDCLASS()
        cls.lpszClassName = "VdictClipboardOwner"  # pyright: ignore[reportAttributeAccessIssue]
        cls.lpfnWndProc = self._wndproc  # pyright: ignore[reportAttributeAccessIssue]
        atom = win32gui.RegisterClass(cls)
        self._hwnd = win32gui.CreateWindow(atom, "vdict", 0, 0, 0, 0, 0, 0, 0, 0, None)

    def _wndproc(self, hwnd, msg, wparam, lparam):
        """WM_RENDERFORMAT is the paste receipt -- a target is asking for the text.
        Never opens the clipboard here: the asking app holds it open."""
        if msg == win32con.WM_RENDERFORMAT:
            win32clipboard.SetClipboardText(self._text, win32con.CF_UNICODETEXT)
            self._served.set()
            return 0
        if msg == win32con.WM_RENDERALLFORMATS:
            if _user32.OpenClipboard(hwnd):
                win32clipboard.SetClipboardText(self._text, win32con.CF_UNICODETEXT)
                _user32.CloseClipboard()
            return 0
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _open_clipboard(self):
        """Another app can hold the clipboard open for a moment at a time."""
        for _ in range(5):
            try:
                win32clipboard.OpenClipboard(self._hwnd)
                return True
            except pywintypes.error:
                time.sleep(0.02)
        return False

    def _snapshot(self):
        """Every readable format, in the order Windows hands them back -- that order
        is what a target uses to pick one, so the restore keeps it."""
        if not self._open_clipboard():
            log("note", "Clipboard busy -- it was not saved this time.")
            return None
        items = []
        try:
            fmt = win32clipboard.EnumClipboardFormats(0)
            while fmt:
                if fmt not in _SKIP_FORMATS:
                    try:
                        items.append((fmt, win32clipboard.GetClipboardData(fmt)))
                    except Exception:
                        pass  # a format that will not read is one we cannot restore
                fmt = win32clipboard.EnumClipboardFormats(fmt)
        finally:
            win32clipboard.CloseClipboard()
        return items

    def _restore(self, items):
        """Writes the saved formats back in their original order."""
        if not self._open_clipboard():
            log("note", "Clipboard busy -- it was not restored this time.")
            return
        try:
            win32clipboard.EmptyClipboard()
            for fmt, data in items:
                try:
                    win32clipboard.SetClipboardData(
                        fmt, _dropfiles(data) if fmt == win32con.CF_HDROP else data)
                except Exception as e:
                    log("note", f"Clipboard format {fmt} not restored: {e}")
        finally:
            win32clipboard.CloseClipboard()

    def _announce(self):
        """Claims the clipboard with a promise of text rather than the text itself.
        The target asking for it is what tells us the paste landed."""
        if not self._open_clipboard():
            return False
        try:
            win32clipboard.EmptyClipboard()
            _user32.SetClipboardData(win32con.CF_UNICODETEXT, None)
            win32clipboard.SetClipboardData(_EXCLUDE_FORMAT, b"\0\0\0\0")
        finally:
            win32clipboard.CloseClipboard()
        return True

    def inject(self, text):
        """Pastes text at the cursor, then restores the clipboard the moment the
        target takes it -- or after the backstop, if nothing ever asks."""
        if not text or not text.strip():
            return

        items = self._snapshot()
        self._text = text + " "
        self._served.clear()
        if not self._announce():
            log("note", "Clipboard busy -- nothing pasted. The text is in this window.")
            return

        pyautogui.hotkey('ctrl', 'v')
        deadline = time.monotonic() + _RECEIPT_TIMEOUT
        while not self._served.is_set() and time.monotonic() < deadline:
            win32gui.PumpWaitingMessages()
            time.sleep(0.001)

        if not self._served.is_set():
            log("note", "Paste did not land -- the text is in this window.")
        if items is not None:
            self._restore(items)
