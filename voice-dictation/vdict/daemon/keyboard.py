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


# Low-level hook values win32con does not define (pynput/mouse/_win32.py:159-160).
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C
LLKHF_INJECTED = 0x10
LLMHF_INJECTED = 0x01

# Hook message -> (button name, pressed). X buttons say which one in mouseData.
_MOUSE_MESSAGES = {
    win32con.WM_RBUTTONDOWN: ("right", True),
    win32con.WM_RBUTTONUP: ("right", False),
    win32con.WM_MBUTTONDOWN: ("middle", True),
    win32con.WM_MBUTTONUP: ("middle", False),
    WM_XBUTTONDOWN: (None, True),
    WM_XBUTTONUP: (None, False),
}

# Swallowing a modifier would break every shortcut that uses it. Bound to PTT,
# these still trigger it but reach Windows too.
_MODIFIER_VKS = frozenset({0x10, 0x11, 0x12, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0x5B, 0x5C})


def _modifier_held():
    """True while Shift, Ctrl or Alt is physically down."""
    return any(win32api.GetAsyncKeyState(vk) & 0x8000 for vk in MODIFIER_VKS)


def _key_vk(name):
    """config.json key name -> the virtual-key code the low-level hook reports."""
    key = getattr(keyboard.Key, name, None)
    if key is not None:
        return key.value.vk
    if len(name) == 1 and win32api.VkKeyScan(name) != -1:
        return win32api.VkKeyScan(name) & 0xFF
    raise ValueError(f"Unsupported PTT key: '{name}'")


def _mouse_name(name, what):
    """config.json mouse name -> the hook's name for it ("side" is x2)."""
    if name not in BUTTON_MAP:
        raise ValueError(f"Unsupported {what}: '{name}'. Supported: {list(BUTTON_MAP)}")
    return BUTTON_MAP[name].name


class PTTListener:
    """Push-to-talk trigger listener (configurable mouse button or keyboard key)"""

    def __init__(self, button="middle", *, enter_button=None, on_enter, on_enter_button):
        """Swallow the PTT trigger and the optional Enter mouse button. on_enter(hwnd)
        fires on every unmodified Enter; on_enter_button() on the hook thread."""
        self.pressed = False
        self.on_enter = on_enter
        self.on_enter_button = on_enter_button

        # Threading events for blocking waits
        self.press_event = threading.Event()
        self.release_event = threading.Event()

        self.ptt_vk = None
        self.ptt_mouse = None
        if button.startswith("key:"):
            self.ptt_vk = _key_vk(button[len("key:"):])
        else:
            self.ptt_mouse = _mouse_name(button, "PTT button")
        self.enter_mouse = (None if enter_button is None
                            else _mouse_name(enter_button, "Enter button"))

        # Always on, whatever the PTT is -- Enter closes a dictation block.
        self.key_listener = keyboard.Listener(
            on_press=self._on_key_press, win32_event_filter=self._key_filter)
        self.mouse_listener = None
        if self.ptt_mouse or self.enter_mouse:
            self.mouse_listener = mouse.Listener(win32_event_filter=self._mouse_filter)

        self.key_listener.start()
        if self.mouse_listener is not None:
            self.mouse_listener.start()

    def _set_pressed(self, pressed):
        """PTT state change. Hook thread -- nothing slower than setting a flag,
        or Windows drops the hook."""
        if pressed == self.pressed:
            return  # key auto-repeat
        self.pressed = pressed
        if pressed:
            self.press_event.set()
            self.release_event.clear()
        else:
            self.release_event.set()
            self.press_event.clear()

    def _key_filter(self, msg, data):
        """Inside Windows' keyboard hook. Takes the PTT key; every other key, and
        every key this app sends itself, passes through untouched."""
        if data.vkCode != self.ptt_vk or data.flags & LLKHF_INJECTED:
            return True
        self._set_pressed(msg in (win32con.WM_KEYDOWN, win32con.WM_SYSKEYDOWN))
        if data.vkCode not in _MODIFIER_VKS:
            # Raises; the hook returns 1 and no program sees the key (win32.py:306).
            self.key_listener.suppress_event()  # pyright: ignore[reportAttributeAccessIssue]
        return True

    def _mouse_filter(self, msg, data):
        """Inside Windows' mouse hook. Takes the PTT and Enter buttons, press and
        release both, so the program under the cursor never sees either."""
        if msg not in _MOUSE_MESSAGES or data.flags & LLMHF_INJECTED:
            return True
        name, pressed = _MOUSE_MESSAGES[msg]
        if name is None:
            name = "x1" if data.mouseData >> 16 == 1 else "x2"
        if name == self.ptt_mouse:
            self._set_pressed(pressed)
        elif name == self.enter_mouse:
            if pressed:
                self.on_enter_button()
        else:
            return True
        self.mouse_listener.suppress_event()  # pyright: ignore[reportAttributeAccessIssue, reportOptionalMemberAccess]

    def _on_key_press(self, key):
        """Internal callback for keyboard press events (runs in background thread)"""
        if key == keyboard.Key.enter and not _modifier_held():
            self.on_enter(win32gui.GetForegroundWindow())

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

    def press_enter(self):
        """A real Enter keystroke, for the Enter mouse button."""
        pyautogui.press("enter")
